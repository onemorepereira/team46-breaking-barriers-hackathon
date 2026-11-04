"""The judge panel (spec AC4, AC8): five cross-family judges read one dossier and score it against the rubric.

Pure parts (dossier, aggregation, agreement) live in analysis.judging; this module only seats the panel, calls
Bedrock and parses replies. The result is archived as runs/<id>/judgement.json, so replay never calls a model.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any

from analysis.judging import dossier as dossier_mod
from analysis.judging import measure, panel
from analysis.judging.rubric import Rubric
from analysis.judging.rubric import load as load_rubric
from analysis.provenance import VALUE_MATCHER_VERSION
from analysis.trace import Run
from core import prompts
from core.store import Store
from harness.config import Config

log = logging.getLogger("harness.judge")
JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
MAX_TOKENS = 8000
Event = Callable[[dict[str, Any]], None]


class JudgeError(Exception):
    pass


@dataclass
class Seat:
    key: str
    model_id: str
    family: str
    recused_for: str | None = None  # the panel judge this reserve replaced (same family as the agent)
    stood_in_for: str | None = None  # the seated judge that failed, whose seat this reserve took


def judging_cfg(cfg: Config) -> dict[str, Any]:
    j = cfg.get("judging") or {}
    if not j.get("panel"):
        raise JudgeError("judging.panel is not set in harness.yaml.")
    return j


def family_of(cfg: Config, key: str | None = None, model_id: str | None = None) -> str:
    models = cfg["models"] or {}
    if key and key in models:
        return str(models[key].get("family") or key)
    for k, m in models.items():
        if model_id and m.get("id") == model_id:
            return str(m.get("family") or k)
    return str(key or model_id or "unknown")


def seats(cfg: Config, agent_key: str | None, agent_model_id: str | None = None) -> list[Seat]:
    """The panel, with same-family judges recused and replaced by reserves (self-preference, GRA §6)."""
    j = judging_cfg(cfg)
    models = cfg["models"] or {}
    for k in [*j["panel"], *(j.get("reserves") or [])]:
        if k not in models:
            raise JudgeError(f"judge {k!r} is not a model in harness.yaml models.")
    agent_family = family_of(cfg, agent_key, agent_model_id)
    recuse = bool(j.get("recuse_same_family", True))
    reserves = [k for k in (j.get("reserves") or []) if k not in j["panel"]]
    out: list[Seat] = []
    for k in j["panel"]:
        fam = family_of(cfg, k)
        if recuse and fam == agent_family:
            sub = next((r for r in reserves if family_of(cfg, r) != agent_family), None)
            if sub is None:
                raise JudgeError(
                    f"judge {k} shares the agent's family ({fam}) and no reserve can replace it."
                )
            reserves.remove(sub)
            out.append(Seat(sub, models[sub]["id"], family_of(cfg, sub), recused_for=k))
        else:
            out.append(Seat(k, models[k]["id"], fam))
    return out


def spare_seats(cfg: Config, agent_key: str | None, panel_seats: list[Seat],
                agent_model_id: str | None = None) -> list[Seat]:  # fmt: skip
    """Reserves not already seated, in order, that share a family with neither the agent nor a seated
    judge. They take the seat of a judge that fails, so the tribunal still has an odd number of votes."""
    j = judging_cfg(cfg)
    models = cfg["models"] or {}
    taken = {family_of(cfg, agent_key, agent_model_id)} | {s.family for s in panel_seats}
    used = {s.key for s in panel_seats}
    out = []
    for k in j.get("reserves") or []:
        fam = family_of(cfg, k)
        if k in used or fam in taken:
            continue
        taken.add(fam)
        out.append(Seat(k, models[k]["id"], fam))
    return out


def system_prompt(r: Rubric) -> str:
    blocks = []
    for c in r.judged:
        anchors = "\n".join(f"  {s}: {c.anchors[s]}" for s in r.scale)
        blocks.append(f"- {c.id} ({c.dimension}): {c.question}\n{anchors}")
    modes = "\n".join(f"- {k}: {v}" for k, v in r.failure_modes.items())
    return prompts.load(
        "judge/system",
        title=r.title,
        scale=", ".join(str(s) for s in r.scale),
        criteria="\n".join(blocks),
        failure_modes=modes,
        criterion_ids=", ".join(c.id for c in r.judged),
    ).strip()


def parse_reply(text: str, r: Rubric, known_refs: set[str]) -> dict[str, Any]:
    """Validate one judge reply. Raises JudgeError with what's wrong (sent back once as a retry hint)."""
    m = JSON_RE.search(text or "")
    if not m:
        raise JudgeError("no JSON object in the reply")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise JudgeError(f"invalid JSON: {e}") from e
    items = data.get("criteria") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise JudgeError("missing 'criteria' list")
    by_id = {str(i.get("id")): i for i in items if isinstance(i, dict)}
    scores, rationales, refs, invalid = {}, {}, {}, 0
    for c in r.judged:
        item = by_id.get(c.id)
        if item is None:
            raise JudgeError(f"criterion {c.id} missing")
        try:
            s = int(item["score"])
        except (KeyError, TypeError, ValueError) as e:
            raise JudgeError(f"criterion {c.id}: score must be one of {list(r.scale)}") from e
        if s not in r.scale or str(item.get("score")).strip() not in {str(x) for x in r.scale}:
            raise JudgeError(f"criterion {c.id}: score must be one of {list(r.scale)}")
        scores[c.id] = s
        rationales[c.id] = str(item.get("rationale", "")).strip()
        cited = [str(x).strip() for x in item.get("refs") or [] if str(x).strip()]
        refs[c.id] = [x for x in cited if x in known_refs]
        invalid += len(cited) - len(refs[c.id])
    modes = [str(x) for x in data.get("failure_modes") or [] if str(x) in r.failure_modes]
    return {"scores": scores, "rationales": rationales, "refs": refs, "failure_modes": sorted(set(modes)),
            "verdict": str(data.get("verdict", "")).strip(), "invalid_refs": invalid}  # fmt: skip


def _bedrock(cfg: Config) -> Any:
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "bedrock-runtime",
        region_name=cfg["region"],
        config=BotoConfig(
            read_timeout=240, connect_timeout=10, retries={"max_attempts": 3, "mode": "adaptive"}
        ),
    )


def _converse(
    client: Any, model_id: str, system: str, messages: list[dict[str, Any]]
) -> tuple[str, dict[str, int]]:
    base = {"modelId": model_id, "system": [{"text": system}], "messages": messages}
    try:
        resp = client.converse(**base, inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0})
    except Exception as e:  # noqa: BLE001 - some models reject temperature; retry without it
        if "temperature" not in str(e).lower():
            raise
        resp = client.converse(**base, inferenceConfig={"maxTokens": MAX_TOKENS})
    blocks = resp["output"]["message"]["content"]
    text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    u = resp.get("usage", {})
    tokens_in = (
        int(u.get("inputTokens", 0))
        + int(u.get("cacheReadInputTokens", 0) or 0)
        + int(u.get("cacheWriteInputTokens", 0) or 0)
    )
    return text, {"input_tokens": tokens_in, "output_tokens": int(u.get("outputTokens", 0))}


def _cost(cfg: Config, key: str, usage: dict[str, int]) -> float | None:
    p = (cfg["prices_per_mtok"] or {}).get(key)
    if not isinstance(p, dict):
        return None
    return round(
        usage["input_tokens"] / 1e6 * float(p["in"]) + usage["output_tokens"] / 1e6 * float(p["out"]), 6
    )


def judge_once(cfg: Config, client: Any, seat: Seat, system: str, dossier_text: str, r: Rubric,
               known_refs: set[str]) -> dict[str, Any]:  # fmt: skip
    """One judge, one pass: call, validate, retry once with the parse error, record usage and cost."""
    t0 = time.monotonic()
    usage = {"input_tokens": 0, "output_tokens": 0}
    messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": dossier_text}]}]
    out: dict[str, Any] = {**asdict(seat), "status": "error"}
    try:
        for attempt in (0, 1):
            text, u = _converse(client, seat.model_id, system, messages)
            usage = {k: usage[k] + u[k] for k in usage}
            try:
                out.update(parse_reply(text, r, known_refs), status="ok", attempts=attempt + 1)
                break
            except JudgeError as e:
                out.update(error=f"parse: {e}", raw_reply=text[-2000:])
                hint = f"Your reply was not valid: {e}. Reply again with only the JSON object."
                messages += [
                    {"role": "assistant", "content": [{"text": text or "(empty)"}]},
                    {"role": "user", "content": [{"text": hint}]},
                ]
    except Exception as e:  # noqa: BLE001 - one judge failing must not stop the panel
        out.update(error=f"{type(e).__name__}: {str(e)[:300]}")
    if out["status"] == "ok":
        out.pop("error", None)
        out.pop("raw_reply", None)
    out.update(usage=usage, cost_usd=_cost(cfg, seat.key, usage), latency_s=round(time.monotonic() - t0, 1))
    return out


def run_panel(cfg: Config, r: Rubric, d: dossier_mod.Dossier, panel_seats: list[Seat], passes: int = 1,
              client: Any = None, on_event: Event | None = None,
              spares: list[Seat] | None = None) -> list[dict[str, Any]]:  # fmt: skip
    """Each pass: the seated judges in parallel, then a spare for each judge that failed (in order)."""
    client = client or _bedrock(cfg)
    system, text = system_prompt(r), dossier_mod.render(d)
    results: list[dict[str, Any]] = []
    for n in range(passes):
        with ThreadPoolExecutor(max_workers=len(panel_seats)) as pool:
            futures = [
                pool.submit(judge_once, cfg, client, s, system, text, r, d.known_refs) for s in panel_seats
            ]
            judges = []
            for f in futures:
                j = f.result()
                judges.append(j)
                if on_event:
                    on_event({"type": "judge", "pass": n + 1, **_judge_summary(r, j)})
        bench = list(spares or [])
        for failed in [j for j in judges if j["status"] != "ok"]:
            if not bench:
                break
            seat = replace(bench.pop(0), stood_in_for=failed["key"])
            j = judge_once(cfg, client, seat, system, text, r, d.known_refs)
            judges.append(j)
            if on_event:
                on_event({"type": "judge", "pass": n + 1, **_judge_summary(r, j)})
        results.append({"pass": n + 1, "judges": judges})
    return results


def _judge_summary(r: Rubric, j: dict[str, Any]) -> dict[str, Any]:
    scores = j.get("scores") or {}
    mean = round(sum(scores.values()) / len(scores) / r.max_score * 100, 1) if scores else None
    return {"key": j["key"], "model_id": j["model_id"], "family": j["family"], "status": j["status"],
            "score": mean, "cost_usd": j.get("cost_usd"), "latency_s": j.get("latency_s"),
            "error": j.get("error"), "stood_in_for": j.get("stood_in_for")}  # fmt: skip


def judge_run(cfg: Config, run: Run, store: Store, passes: int | None = None, client: Any = None,
              on_event: Event | None = None) -> dict[str, Any]:  # fmt: skip
    """Judge an archived run and write runs/<id>/judgement.json. Returns the judgement.

    A run whose model calls all failed (an infrastructure error) is not sent to the panel: the record
    says "not scored" with the cause, replaces any earlier judgement, and stays out of agreement."""
    cause = measure.infrastructure_failure(run)
    if cause:
        record = not_scored(run, cause)
        store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(record, indent=1))
        if on_event:
            on_event({"type": "not_scored", "cause": cause})
        return record
    j = judging_cfg(cfg)
    r = load_rubric(j["rubric"])
    passes = int(passes or j.get("passes") or 1)
    d = dossier_mod.build(run)
    panel_seats = seats(cfg, run.manifest.get("model_key"), run.manifest.get("model_id"))
    if on_event:
        on_event({"type": "judging", "seats": [asdict(s) for s in panel_seats], "passes": passes})
    spares = spare_seats(cfg, run.manifest.get("model_key"), panel_seats, run.manifest.get("model_id"))
    pass_results = run_panel(cfg, r, d, panel_seats, passes, client, on_event, spares)
    judgement = assemble(r, run, pass_results, panel_seats)
    store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(judgement, indent=1))
    return judgement


def not_scored(run: Run, cause: str) -> dict[str, Any]:
    """The judgement record for a run the panel can't judge (Run.judgement reads it as None)."""
    return {
        "schema_version": 1,
        "run_id": run.run_id,
        "judged_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "not_scored": {"reason": "infrastructure", "cause": cause},
        "judging_cost_usd": 0.0,
    }


def assemble(
    r: Rubric, run: Run, pass_results: list[dict[str, Any]], panel_seats: list[Seat]
) -> dict[str, Any]:
    m = measure.measure(run)
    result = panel.aggregate(r, pass_results, m)
    cost = sum(j.get("cost_usd") or 0 for p in pass_results for j in p["judges"])
    return {
        "schema_version": 1,
        "run_id": run.run_id,
        "judged_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rubric": {"id": r.id, "version": r.version, "sha256": r.sha256, "snapshot": r.raw},
        "seats": [asdict(s) for s in panel_seats],
        "passes": pass_results,
        "panel": result.as_dict(),
        "value_matcher_version": VALUE_MATCHER_VERSION,
        "judging_cost_usd": round(cost, 6),
    }


rescore = panel.rescore  # replay: re-aggregate an archived judgement, no model calls
