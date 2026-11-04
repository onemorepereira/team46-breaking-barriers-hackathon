"""Human feedback for the judges (docs/judge-feedback): reviews, reconsideration, and deployment guidance.

Reviews and guidance live in the deployment's own archive (`archive_uri`) under `feedback/`, so they're scoped
to one Foundry instance and never live in the repo or the browser. Run-scoped results (a revised judgement,
earlier judgements) go to the run's own store, as judging does.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Any

from analysis.judging import dossier as dossier_mod
from analysis.judging import feedback as fb
from analysis.judging.rubric import Rubric, parse
from analysis.judging.rubric import load as load_rubric
from analysis.trace import Run
from core import prompts
from core.store import Store, open_store
from harness import judge
from harness.config import Config

log = logging.getLogger("harness.feedback")
MIN_HELD_OUT = 5
FALLBACK_PASS_USD = 0.31


class Conflict(fb.FeedbackError):
    """The request is valid but the state doesn't allow it (HTTP 409)."""


class NotFound(fb.FeedbackError):
    """No such review or guidance version (HTTP 404)."""


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def deployment_store(cfg: Config) -> Store:
    return open_store(cfg["archive_uri"])


def active_rubric(cfg: Config) -> Rubric:
    return load_rubric(judge.judging_cfg(cfg)["rubric"])


def _read(store: Store, key: str) -> dict[str, Any] | None:
    text = store.read_text(key)
    return json.loads(text) if text else None


def _write(store: Store, key: str, obj: dict[str, Any]) -> None:
    store.write_text(key, json.dumps(obj, indent=1))


# ---- Reviews ----

REVIEWS = "feedback/reviews"


def all_reviews(store: Store) -> list[dict[str, Any]]:
    out = []
    for key in store.list(REVIEWS):
        if key.endswith(".json"):
            rv = _read(store, key)
            if rv:
                out.append(rv)
    return sorted(out, key=lambda r: r.get("created_at", ""))


def run_reviews(store: Store, run: Run) -> list[dict[str, Any]]:
    """The run's reviews, newest first; `current` says whether each reviews the current judgement, and a
    review the current judgement's revision names reads as reconsidered (crash repair, design: Reviews)."""
    jd = run.judgement or {}
    revised_by = (jd.get("revision") or {}).get("review_id")
    out = []
    for key in store.list(f"feedback/runs/{run.run_id}"):
        rv = _read(store, key) if key.endswith(".json") else None
        if not rv:
            continue
        if rv["id"] == revised_by and not rv.get("reconsidered"):
            rv["reconsidered"] = jd.get("judged_at")
        rv["current"] = bool(jd) and rv.get("judged_at") == jd.get("judged_at")
        out.append(rv)
    return sorted(out, key=lambda r: r.get("created_at", ""), reverse=True)


def _save_review(store: Store, rv: dict[str, Any]) -> None:
    rv = {k: v for k, v in rv.items() if k != "current"}
    _write(store, f"{REVIEWS}/{rv['id']}.json", rv)
    _write(store, f"feedback/runs/{rv['run_id']}/{rv['id']}.json", rv)


def get_review(store: Store, review_id: str) -> dict[str, Any]:
    if not review_id.startswith("r-") or "/" in review_id:
        raise NotFound("unknown review")
    rv = _read(store, f"{REVIEWS}/{review_id}.json")
    if not rv:
        raise NotFound("unknown review")
    return rv


def create_review(cfg: Config, store: Store, run: Run, body: dict[str, Any]) -> dict[str, Any]:
    """Validate and store one review of the run's current judgement (AC1, AC5)."""
    if run.not_scored:
        raise Conflict("This run wasn't scored (no model call succeeded), so there's nothing to review.")
    jd = run.judgement
    if not jd:
        raise Conflict("This run hasn't been judged yet.")
    r = parse(jd["rubric"]["snapshot"])
    d = dossier_mod.build(run)
    checked = fb.validate_review(body, r, d.known_refs, jd)
    rv = {
        "schema_version": 1,
        "id": f"r-{secrets.token_hex(6)}",
        "run_id": run.run_id,
        "reviewer": checked["reviewer"],
        "created_at": now(),
        "judged_at": jd.get("judged_at"),
        "rubric": {"id": r.id, "version": r.version},
        "guidance_version": (jd.get("guidance") or {}).get("version"),
        "criteria": checked["criteria"],
        "note": str(body.get("note") or "").strip(),
        "measured_note": str(body.get("measured_note") or "").strip(),
        "reconsidered": None,
    }
    _save_review(store, rv)
    return rv


# ---- Reconsideration ----


def parse_reconsider(text: str, r: Rubric, known_refs: set[str], earlier: dict[str, int]) -> dict[str, Any]:
    """parse_reply plus `changed` and `response` per criterion (AC3)."""
    out = judge.parse_reply(text, r, known_refs)
    m = judge.JSON_RE.search(text or "")
    data = json.loads(m.group(0)) if m else {}
    by_id = {str(i.get("id")): i for i in data.get("criteria", []) if isinstance(i, dict)}
    changed, responses = {}, {}
    for c in r.judged:
        item = by_id.get(c.id, {})
        changed[c.id] = earlier.get(c.id) is not None and out["scores"][c.id] != earlier[c.id]
        responses[c.id] = str(item.get("response") or "").strip()[:500]
    return {**out, "changed": changed, "responses": responses}


def _pass1_valid(jd: dict[str, Any]) -> list[dict[str, Any]]:
    return [j for j in ((jd.get("passes") or [{}])[0]).get("judges", []) if j.get("status") == "ok"]


def called_seats(jd: dict[str, Any]) -> list[judge.Seat]:
    """The judges that voted validly in pass 1 of the reviewed judgement, stand-ins included (design 3)."""
    return [
        judge.Seat(j["key"], j["model_id"], j["family"], j.get("recused_for"), j.get("stood_in_for"))
        for j in _pass1_valid(jd)
    ]


def _reply_json(j: dict[str, Any] | None, r: Rubric) -> str:
    if not j:
        return "(You were not on the panel for the first judgement, so there is no earlier reply.)"
    crit = [
        {
            "id": c.id,
            "rationale": (j.get("rationales") or {}).get(c.id, ""),
            "refs": (j.get("refs") or {}).get(c.id, []),
            "score": (j.get("scores") or {}).get(c.id),
        }
        for c in r.judged
    ]
    return json.dumps(
        {"criteria": crit, "failure_modes": j.get("failure_modes", []), "verdict": j.get("verdict", "")},
        indent=1,
    )


def reconsider_pass(
    cfg: Config,
    r: Rubric,
    d: dossier_mod.Dossier,
    jd: dict[str, Any],
    review: dict[str, Any],
    called: list[judge.Seat],
    spares: list[judge.Seat],
    guidance: dict[str, Any] | None,
    client: Any = None,
    on_event: judge.Event | None = None,
) -> list[dict[str, Any]]:
    """One reconsideration pass (design steps 3–7): each judge sees the dossier, its own earlier reply and the
    review; then a spare for each judge that failed, with no earlier reply."""
    system = judge.system_prompt(r, guidance) + "\n\n" + prompts.load("judge/reconsider", _="").strip()
    base = dossier_mod.render(d)
    review_text = fb.render_review(review)
    earlier = {j["key"]: j for j in _pass1_valid(jd)}

    def message(seat: judge.Seat) -> str:
        return (
            f"{base}\n\n<your_earlier_reply>\n{_reply_json(earlier.get(seat.key), r)}\n</your_earlier_reply>"
            f'\n\n<human_review reviewer="{fb.escape(review.get("reviewer", ""))}">\n{review_text}\n'
            "</human_review>"
        )

    def call(seat: judge.Seat) -> dict[str, Any]:
        scores = {k: int(v) for k, v in ((earlier.get(seat.key) or {}).get("scores") or {}).items()}
        return judge.judge_once(
            cfg,
            client,
            seat,
            system,
            message(seat),
            r,
            d.known_refs,
            lambda text, rr, refs: parse_reconsider(text, rr, refs, scores),
        )

    client = client or judge._bedrock(cfg)
    taken = {s.family for s in called}
    bench = [s for s in spares if s.family not in taken and s.key not in {c.key for c in called}]
    with ThreadPoolExecutor(max_workers=max(1, len(called))) as pool:
        judges = list(pool.map(call, called))
    for j in judges:
        if on_event:
            on_event({"type": "judge", "pass": 1, **judge._judge_summary(r, j)})
    for failed in [j for j in judges if j["status"] != "ok"]:
        if not bench:
            break
        j = call(replace(bench.pop(0), stood_in_for=failed["key"]))
        judges.append(j)
        if on_event:
            on_event({"type": "judge", "pass": 1, **judge._judge_summary(r, j)})
    return [{"pass": 1, "judges": judges}]


def reconsider(
    cfg: Config,
    run: Run,
    run_store: Store,
    deploy: Store,
    review_id: str,
    client: Any = None,
    on_event: judge.Event | None = None,
) -> dict[str, Any]:
    """The same seated judges reconsider the run with the review (AC3, AC4). Returns the new judgement."""
    if not (cfg.get("judging") or {}).get("reconsider", True):
        raise Conflict("Reconsideration is switched off for this deployment (judging.reconsider).")
    review = get_review(deploy, review_id)
    if review.get("run_id") != run.run_id:
        raise NotFound("that review is of another run")
    if review.get("reconsidered"):
        raise Conflict("The judges already reconsidered this review.")
    jd = run.judgement
    if not jd or jd.get("judged_at") != review.get("judged_at"):
        raise Conflict("This review is of an older judgement; review the current one.")
    r = parse(jd["rubric"]["snapshot"])
    d = dossier_mod.build(run)
    g = jd.get("guidance")  # the reviewed judgement's own guidance, so the revision isolates the review
    guidance = {"version": g["version"], "lessons": g.get("snapshot") or []} if g else None
    called = called_seats(jd)
    if len(called) < 3:
        raise Conflict("The reviewed judgement has fewer than 3 valid votes to reconsider.")
    spares = judge.spare_seats(cfg, run.manifest.get("model_key"), called, run.manifest.get("model_id"))
    if on_event:
        on_event(
            {
                "type": "judging",
                "seats": [asdict(s) for s in called],
                "passes": 1,
                "reconsider": review_id,
                "guidance": guidance and guidance["version"],
            }
        )
    passes = reconsider_pass(cfg, r, d, jd, review, called, spares, guidance, client, on_event)
    valid = [j for j in passes[0]["judges"] if j.get("status") == "ok"]
    if len(valid) < 3:
        raise judge.JudgeError(f"only {len(valid)} judges answered; nothing was changed")
    new = judge.assemble(r, run, passes, called, guidance)
    new["revision"] = {
        "review_id": review_id,
        "reviewer": review["reviewer"],
        "previous": jd.get("judged_at"),
        "at": new["judged_at"],
        "prompt_sha256": prompt_sha("judge/reconsider"),
    }
    judge.keep_previous(run_store, run.run_id)
    run_store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(new, indent=1))
    review["reconsidered"] = new["judged_at"]
    _save_review(deploy, review)
    return new


def prompt_sha(name: str) -> str:
    return hashlib.sha256(prompts.path(name).read_bytes()).hexdigest()


def previous_judgement(run_store: Store, run_id: str, judged_at: str) -> dict[str, Any] | None:
    if "/" in judged_at or ".." in judged_at:
        return None
    return _read(run_store, f"runs/{run_id}/judgements/{judged_at}.json")


# ---- Guidance versions ----


def gpath(r: Rubric) -> str:
    return f"feedback/guidance/{r.id}-v{r.version}"


def active_pointer(store: Store, r: Rubric) -> dict[str, Any]:
    """active.json: the one source of truth for which version is active (design: Where things live)."""
    return _read(store, f"{gpath(r)}/active.json") or {"version": None}


def _with_status(v: dict[str, Any], active: int | None) -> dict[str, Any]:
    if active is not None and int(v["version"]) == int(active):
        v["status"] = "active"
    else:
        v["status"] = "retired" if v.get("approvals") else "draft"
    return v


def versions(store: Store, r: Rubric) -> list[dict[str, Any]]:
    active = active_pointer(store, r).get("version")
    out = [
        _with_status(v, active)
        for k in store.list(f"{gpath(r)}/versions")
        if k.endswith(".json") and (v := _read(store, k))
    ]
    return sorted(out, key=lambda v: int(v["version"]))


def get_version(store: Store, r: Rubric, n: int) -> dict[str, Any]:
    v = _read(store, f"{gpath(r)}/versions/{int(n)}.json")
    if not v:
        raise NotFound(f"no guidance version {n} for {r.id} v{r.version}")
    return _with_status(v, active_pointer(store, r).get("version"))


def _save_version(store: Store, r: Rubric, v: dict[str, Any]) -> None:
    v = {k: val for k, val in v.items() if k != "status"}  # status is derived on read, never stored
    v["sha256"] = fb.guidance_sha(v)
    _write(store, f"{gpath(r)}/versions/{int(v['version'])}.json", v)


def active_version(cfg: Config, r: Rubric, store: Store | None = None) -> dict[str, Any] | None:
    """The active version for this rubric in this deployment, or None (AC12, AC13)."""
    if store is None:
        if not cfg.get("archive_uri"):
            return None  # no deployment archive configured (e.g. a bare test config): no guidance
        store = deployment_store(cfg)
    n = active_pointer(store, r).get("version")
    if n is None:
        return None
    v = get_version(store, r, int(n))
    if len(fb.render_lessons(v.get("lessons") or [], r)) > fb.GUIDANCE_CHARS_MAX:
        log.warning("guidance v%s is over the prompt budget; judging without it", n)
        return None
    return v


def log_entries(store: Store, r: Rubric) -> list[dict[str, Any]]:
    """Newest first. `seq` (nanoseconds) orders changes made within the same second."""
    out = [e for k in store.list(f"{gpath(r)}/log") if k.endswith(".json") and (e := _read(store, k))]
    return sorted(out, key=lambda e: (e.get("at", ""), e.get("seq", 0)), reverse=True)


def _log(store: Store, r: Rubric, entry: dict[str, Any]) -> None:
    entry["seq"] = time.time_ns()
    _write(store, f"{gpath(r)}/log/{entry['seq']}.json", entry)


def rubric_reviews(store: Store, r: Rubric) -> list[dict[str, Any]]:
    return [rv for rv in all_reviews(store) if rv.get("rubric") == {"id": r.id, "version": r.version}]


def chair_call(cfg: Config, system: str, message: str, client: Any = None) -> tuple[str, dict[str, Any]]:
    """One call to the chair model (judging.panel[0]); returns (text, {model, cost_usd})."""
    key = judge.judging_cfg(cfg)["panel"][0]
    model_id = cfg["models"][key]["id"]
    text, usage = judge._converse(
        client or judge._bedrock(cfg), model_id, system, [{"role": "user", "content": [{"text": message}]}]
    )
    return text, {"model": key, "cost_usd": judge._cost(cfg, key, usage) or 0.0}


def _lessons_from(text: str, r: Rubric, known: set[str]) -> tuple[list[dict[str, Any]], int]:
    m = judge.JSON_RE.search(text or "")
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError as e:
        raise fb.FeedbackError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
        raise fb.FeedbackError("the reply has no 'lessons' list")
    return fb.validate_lessons(data["lessons"], r, known, require_sources=True)


def propose(cfg: Config, store: Store, by: str, client: Any = None) -> dict[str, Any]:
    """Draft a new version from the disagreements in the **train** runs' reviews (AC8)."""
    by = fb._name(by, "Your name")
    r = active_rubric(cfg)
    train = [rv for rv in rubric_reviews(store, r) if not fb.held_out(rv["run_id"])]
    disagreements = [
        (rv, cid, c)
        for rv in train
        for cid, c in rv.get("criteria", {}).items()
        if not c.get("agree") and c.get("panel_median") is not None and c.get("score") != c["panel_median"]
    ]
    if not disagreements:
        raise Conflict(
            "No review of a training run disagrees with the panel yet, so there's nothing to learn "
            "from. (About a third of reviewed runs are held out for evaluation.)"
        )
    current = active_version(cfg, r, store)
    criteria = "\n".join(
        f"- {c.id}: {c.question}\n" + "\n".join(f"  {s}: {c.anchors[s]}" for s in r.scale) for c in r.judged
    )
    system = prompts.load(
        "judge/guidance_propose",
        title=r.title,
        criteria=criteria,
        max_lessons=fb.LESSONS_MAX,
        current=json.dumps((current or {}).get("lessons") or [], indent=1),
    ).strip()
    body = "\n\n".join(
        f'<review id="{rv["id"]}" criterion="{cid}" panel="{c["panel_median"]}" human="{c["score"]}">\n'
        f"{fb.escape(c.get('reason', ''))}\n</review>"
        for rv, cid, c in disagreements
    )
    known = {rv["id"] for rv in train}
    text, meta = chair_call(cfg, system, body, client)
    try:
        lessons, dropped = _lessons_from(text, r, known)
    except fb.FeedbackError as e:
        hint = f"\n\nYour reply was not valid ({e}). Reply again with only the JSON object."
        text, meta2 = chair_call(cfg, system, body + hint, client)
        meta["cost_usd"] += meta2["cost_usd"]
        try:
            lessons, dropped = _lessons_from(text, r, known)
        except fb.FeedbackError as e2:
            raise judge.JudgeError(f"the proposal model's reply was unusable twice: {e2}") from e2
    v: dict[str, Any] = {
        "schema_version": 1,
        "version": max((int(x["version"]) for x in versions(store, r)), default=0) + 1,
        "rubric": {"id": r.id, "version": r.version},
        "created_at": now(),
        "created_by": by,
        "based_on": (current or {}).get("version"),
        "lessons": lessons,
        "proposal": {
            "model": meta["model"],
            "reviews_read": len(train),
            "disagreements": len(disagreements),
            "dropped": dropped,
            "cost_usd": round(meta["cost_usd"], 4),
            "prompt_sha256": prompt_sha("judge/guidance_propose"),
        },
        "approvals": [],
        "latest_evaluation": None,
    }
    _save_version(store, r, v)
    return get_version(store, r, int(v["version"]))


def edit(cfg: Config, store: Store, n: int, lessons: Any) -> dict[str, Any]:
    """Replace a draft's lessons by hand (AC9). Only a never-approved draft is editable."""
    r = active_rubric(cfg)
    v = get_version(store, r, n)
    if v["status"] != "draft":
        raise Conflict(f"Version {n} is {v['status']}; only a draft can be edited.")
    v["lessons"] = fb.check_edit(lessons, r, {rv["id"] for rv in rubric_reviews(store, r)})
    v["edited_at"] = now()
    v["latest_evaluation"] = None  # an edit invalidates the last evaluation
    _save_version(store, r, v)
    return get_version(store, r, n)


def evaluation_counts(v: dict[str, Any]) -> bool:
    ev = v.get("latest_evaluation") or {}
    return ev.get("verdict") == "adopt" and ev.get("sha256") == fb.guidance_sha(v)


def approve(cfg: Config, store: Store, n: int, by: str, reason: str = "") -> dict[str, Any]:
    """Make version n active for the deployment (AC11); approving a retired version is a rollback."""
    by = fb._name(by, "Your name")
    reason = str(reason or "").strip()
    if len(reason) > fb.NOTE_MAX:
        raise fb.FeedbackError(f"The reason is longer than {fb.NOTE_MAX} characters.")
    r = active_rubric(cfg)
    v = get_version(store, r, n)
    if v["status"] == "active":
        raise Conflict(f"Version {n} is already active.")
    if not evaluation_counts(v) and not reason:
        raise fb.FeedbackError(
            "This version hasn't been evaluated as 'adopt' (in its current form); give a "
            "reason to approve it anyway."
        )
    if len(fb.render_lessons(v.get("lessons") or [], r)) > fb.GUIDANCE_CHARS_MAX:
        raise fb.FeedbackError(f"The lessons are over the {fb.GUIDANCE_CHARS_MAX}-character prompt budget.")
    previous = active_pointer(store, r).get("version")
    at = now()
    verdict = (v.get("latest_evaluation") or {}).get("verdict") if evaluation_counts(v) else None
    v.setdefault("approvals", []).append({"by": by, "at": at, "reason": reason, "evaluation": verdict})
    _save_version(store, r, v)
    _write(store, f"{gpath(r)}/active.json", {"version": int(n), "by": by, "at": at, "reason": reason})
    _log(
        store,
        r,
        {
            "action": "approve",
            "version": int(n),
            "previous": previous,
            "by": by,
            "at": at,
            "reason": reason,
            "evaluation_verdict": verdict,
        },
    )
    return get_version(store, r, n)


def switch_off(cfg: Config, store: Store, by: str, reason: str = "") -> dict[str, Any]:
    by = fb._name(by, "Your name")
    r = active_rubric(cfg)
    previous = active_pointer(store, r).get("version")
    pointer = {"version": None, "by": by, "at": now(), "reason": str(reason or "").strip()[: fb.NOTE_MAX]}
    _write(store, f"{gpath(r)}/active.json", pointer)
    _log(
        store,
        r,
        {
            "action": "off",
            "version": None,
            "previous": previous,
            "by": by,
            "at": pointer["at"],
            "reason": pointer["reason"],
            "evaluation_verdict": None,
        },
    )
    return pointer


# ---- Evaluation ----


def held_out_scores(store: Store, r: Rubric) -> dict[str, dict[str, dict[str, Any]]]:
    """Held-out reviewed runs for this rubric: run_id -> criterion -> human score (design: Evaluation)."""
    reviews = [rv for rv in rubric_reviews(store, r) if fb.held_out(rv["run_id"])]
    return fb.human_scores(reviews)


def _run(cfg: Config, index: Any, run_id: str) -> tuple[Run, Store]:
    store = open_store(index.run_uri(run_id) or cfg["archive_uri"])
    return Run.load(store, run_id), store


def estimate(cfg: Config, store: Store, index: Any, n: int) -> dict[str, Any]:
    r = active_rubric(cfg)
    get_version(store, r, n)
    runs = held_out_scores(store, r)
    costs = []
    for run_id in list(runs)[:10]:
        try:
            jd = _run(cfg, index, run_id)[0].judgement
        except Exception:  # noqa: BLE001 - an estimate only
            continue
        if jd and jd.get("judging_cost_usd"):
            costs.append(float(jd["judging_cost_usd"]))
    per = sum(costs) / len(costs) if costs else FALLBACK_PASS_USD
    passes = 2 * len(runs) + 4 if len(runs) >= MIN_HELD_OUT else 0
    reviewed = {rv["run_id"] for rv in rubric_reviews(store, r)}
    return {
        "held_out": len(runs),
        "reviewed_runs": len(reviewed),
        "min_held_out": MIN_HELD_OUT,
        "passes": passes,
        "estimate_usd": round(passes * per, 2),
    }


def evaluate(
    cfg: Config, store: Store, index: Any, n: int, client: Any = None, on_event: judge.Event | None = None
) -> dict[str, Any]:
    """Judge each held-out run with the live guidance and with version n; compare with humans; calibrate."""
    from harness import calibrate

    r = active_rubric(cfg)
    v = get_version(store, r, n)
    if len(fb.render_lessons(v.get("lessons") or [], r)) > fb.GUIDANCE_CHARS_MAX:
        raise fb.FeedbackError(f"The lessons are over the {fb.GUIDANCE_CHARS_MAX}-character prompt budget.")
    baseline = active_version(cfg, r, store)
    if baseline and int(baseline["version"]) == int(n):
        baseline = None  # evaluating the active version: compare it with no guidance
    runs = held_out_scores(store, r)
    report: dict[str, Any] = {
        "schema_version": 1,
        "version": int(n),
        "sha256": fb.guidance_sha(v),
        "at": now(),
        "baseline": baseline and baseline["version"],
        "held_out": sorted(runs),
        "excluded": [],
        "cost_usd": 0.0,
    }

    def finish(rep: dict[str, Any]) -> dict[str, Any]:
        rep["cost_usd"] = round(rep["cost_usd"], 4)
        _write(store, f"{gpath(r)}/evals/{int(n)}-{rep['at'].replace(':', '')}.json", rep)
        fresh = get_version(store, r, n)
        fresh["latest_evaluation"] = {
            k: rep.get(k) for k in ("at", "verdict", "reasons", "sha256", "cost_usd")
        }
        _save_version(store, r, fresh)
        if on_event:
            on_event({"type": "evaluated", "verdict": rep["verdict"], "reasons": rep.get("reasons")})
        return rep

    def short(count: int) -> dict[str, Any]:
        return finish(
            {
                **report,
                "verdict": "insufficient_evidence",
                "reasons": [f"{count} usable held-out reviewed runs; at least {MIN_HELD_OUT} are needed"],
            }
        )

    if len(runs) < MIN_HELD_OUT:
        return short(len(runs))
    client = client or judge._bedrock(cfg)
    rows: list[dict[str, Any]] = []
    latest: tuple[str, Run | None] = ("", None)
    reviews = rubric_reviews(store, r)
    for i, (run_id, crit) in enumerate(sorted(runs.items()), 1):
        try:
            run, _ = _run(cfg, index, run_id)
        except Exception as e:  # noqa: BLE001 - excluded and counted (design: Evaluation, step 1)
            log.warning("evaluation: can't load %s: %s", run_id, e)
            report["excluded"].append(run_id)
            continue
        d = dossier_mod.build(run)
        seats = judge.seats(cfg, run.manifest.get("model_key"), run.manifest.get("model_id"))
        spares = judge.spare_seats(cfg, run.manifest.get("model_key"), seats, run.manifest.get("model_id"))
        meds = {}
        for label, g in (("without", baseline), ("with", v)):
            ps = judge.run_panel(cfg, r, d, seats, 1, client, None, spares, g)
            report["cost_usd"] += sum(j.get("cost_usd") or 0 for p in ps for j in p["judges"])
            meds[label] = calibrate._medians(r, ps)
        if any(all(m is None for m in meds[k].values()) for k in meds):
            report["excluded"].append(run_id)
        else:
            rows += [
                {
                    "run_id": run_id,
                    "criterion": cid,
                    "human": c["human"],
                    "without": meds["without"].get(cid),
                    "with": meds["with"].get(cid),
                }
                for cid, c in crit.items()
            ]
            created = max((rv["created_at"] for rv in reviews if rv["run_id"] == run_id), default="")
            if created >= latest[0]:
                latest = (created, run)
        if on_event:
            on_event({"type": "evaluating", "done": i, "total": len(runs), "run_id": run_id})
    usable = len(runs) - len(report["excluded"])
    if usable < MIN_HELD_OUT or latest[1] is None:
        return short(usable)
    metrics = fb.compare(rows)
    if on_event:
        on_event({"type": "evaluating", "stage": "calibration", "run_id": latest[1].run_id})
    cal = calibrate.calibrate(cfg, latest[1], None, client=client, guidance=v, write=False)
    report["cost_usd"] += cal.get("cost_usd") or 0
    reasons = []
    if not metrics["improved"]:
        reasons.append("agreement with reviewers didn't improve (overall mean absolute difference)")
    reasons += [f"{cid}: mean absolute difference rose by more than 0.25" for cid in metrics["rises"]]
    if cal.get("exit_code") == 1:
        reasons.append(
            "planted-defect calibration failed with this guidance (a planted defect went unnoticed)"
        )
    report.update(
        rows=rows,
        metrics=metrics,
        calibration={
            "run_id": latest[1].run_id,
            "rows": cal.get("rows"),
            "exit_code": cal.get("exit_code"),
            "applicable": cal.get("exit_code") != 2,
        },
        verdict="adopt" if not reasons else "dont_adopt",
        reasons=reasons,
    )
    return finish(report)


def evaluations(store: Store, r: Rubric, n: int) -> list[dict[str, Any]]:
    keys = [k for k in store.list(f"{gpath(r)}/evals") if k.rsplit("/", 1)[-1].startswith(f"{int(n)}-")]
    return sorted((e for k in keys if (e := _read(store, k))), key=lambda e: e.get("at", ""), reverse=True)


# ---- Summary for the API and CLI ----


def overview(cfg: Config, store: Store) -> dict[str, Any]:
    """GET /api/guidance: the active rubric and version, all versions, the log, and agreement (AC14)."""
    r = active_rubric(cfg)
    mine = rubric_reviews(store, r)
    reviewed = {rv["run_id"] for rv in mine}
    return {
        "rubric": {"id": r.id, "version": r.version, "title": r.title},
        "enabled": bool((cfg.get("judging") or {}).get("guidance", True)),
        "active": active_pointer(store, r),
        "versions": [
            {
                k: v.get(k)
                for k in (
                    "version",
                    "status",
                    "created_at",
                    "created_by",
                    "based_on",
                    "approvals",
                    "latest_evaluation",
                    "sha256",
                )
            }
            | {"lessons": len(v.get("lessons") or []), "evaluation_current": evaluation_counts(v)}
            for v in reversed(versions(store, r))
        ],
        "log": log_entries(store, r),
        "reviews": len(mine),
        "reviewed_runs": len(reviewed),
        "held_out_runs": sum(1 for x in reviewed if fb.held_out(x)),
        "min_held_out": MIN_HELD_OUT,
        "agreement": fb.human_agreement(fb.human_scores(mine)),
        "criteria": [{"id": c.id, "question": c.question} for c in r.judged],
    }
