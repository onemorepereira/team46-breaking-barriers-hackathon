"""Visual check of a run's reported sites (docs/visual-check): the sharpest open image of each, and a vision
model's verdict on whether the requested asset is there.

Archived as runs/<id>/visual.json plus runs/<id>/visual/<site_id>.jpg, like conditions.json: replay and
rescore read the archive and never call a model. Workers only fetch and ask; this module's own thread writes
the archive once, after the deadline, so nothing lands later.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime
from typing import Any

from analysis.judging import measure
from analysis.judging.visual import load, summary  # noqa: F401 - summary is re-exported for callers
from analysis.trace import Run
from core import prompts
from harness import sharp

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "enabled": False,  # on in harness.yaml; a config without the block doesn't reach the network
    "sources": list(sharp.SOURCES),
    "models": ["opus", "kimi", "grok"],
    "max_sites": 12,
    "window_m": 250,
    "deadline_s": 60,
}
WORKERS = 6
S2_MIN_M = 1280  # a 10 m image needs a wider window to show anything (128 px native)
FINAL = ("present", "absent", "unclear", "no_image")
VERDICTS = ("present", "absent", "unclear")
REASON_MAX = 300
TEXT_MAX = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def settings(cfg: Any) -> dict[str, Any]:
    return {**DEFAULTS, **(cfg.get("visual_check") or {})}


def site_id(lat: float, lon: float) -> str:
    return hashlib.sha256(f"{lat:.4f},{lon:.4f}".encode()).hexdigest()[:12]


def _clean(text: Any, limit: int) -> str:
    return _CONTROL.sub(" ", str(text or "")).strip()[:limit]


def _square(lat: float, lon: float, metres: float) -> list[float]:
    d = metres / 2 / 111_320
    e = d / max(math.cos(math.radians(lat)), 0.01)
    return [round(lon - e, 6), round(lat - d, 6), round(lon + e, 6), round(lat + d, 6)]


def _at_least(bbox: list[float], lat: float, lon: float, metres: float) -> list[float]:
    """bbox, widened to at least `metres` square around (lat, lon)."""
    w, s, e, n = bbox
    width_m = (e - w) * 111_320 * math.cos(math.radians(lat))
    height_m = (n - s) * 111_320
    if min(width_m, height_m) >= metres:
        return bbox
    return _square(lat, lon, max(metres, width_m, height_m))


def sites(run: Run, max_sites: int, window_m: float) -> list[dict[str, Any]]:
    """The reported sites: coordinate claims, de-duplicated by position, each matched to an LGND chip when one
    sits at the same position or the claim cites its node."""
    located = measure.measure(run).located
    chips = [x for x in located if x.source == "chip" and x.bbox]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for x in located:
        if x.source != "claim":
            continue
        sid = site_id(x.lat, x.lon)
        if sid in seen:
            continue
        seen.add(sid)
        claim = x.claim or x.label or ""
        chip = next(
            (c for c in chips if (round(c.lat, 4), round(c.lon, 4)) == (round(x.lat, 4), round(x.lon, 4))),
            None,
        ) or next(
            (c for c in chips if c.node and re.search(rf"(?<![\w/:]){re.escape(c.node)}(?!\w)", claim)), None
        )
        out.append(
            {
                "site_id": sid,
                "claim": _clean(claim, 500),
                "lat": round(x.lat, 6),
                "lon": round(x.lon, 6),
                "bbox": [round(float(v), 6) for v in chip.bbox]
                if chip and chip.bbox
                else _square(x.lat, x.lon, window_m),
                "chip_node": chip.node if chip else None,
                "observed": chip.observed if chip else None,
                "index": chip.index if chip else None,
            }
        )
        if len(out) >= max_sites:
            break
    return out


def checker(cfg: Any, run: Run, keys: list[str]) -> str | None:
    """The first listed model not sharing the agent's family (the panel's recusal rule)."""
    from harness.judge import family_of

    agent = family_of(cfg, run.manifest.get("model_key"), run.manifest.get("model_id"))
    models = cfg["models"] or {}
    return next((k for k in keys if k in models and family_of(cfg, k) != agent), None)


def parse(text: str) -> tuple[str, str]:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    data, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(data, dict) or data.get("verdict") not in VERDICTS:
        raise ValueError('"verdict" must be "present", "absent" or "unclear"')
    return str(data["verdict"]), _clean(data.get("reason"), REASON_MAX)


def _fence(text: str) -> str:
    return text.replace("<", "‹").replace(">", "›")


def _check_one(
    cfg: Any,
    client: Any,
    key: str,
    request: str,
    site: dict[str, Any],
    sources: list[str],
    stop: threading.Event,
) -> tuple[dict[str, Any], bytes | None]:
    from harness.judge import _converse, _cost

    rec = {k: site[k] for k in ("site_id", "claim", "lat", "lon", "bbox", "chip_node")}
    tried: list[str] = []
    rec["tried"] = tried
    lat, lon = site["lat"], site["lon"]
    jpeg, img, box = None, None, site["bbox"]
    for cand in sharp.candidates(
        lat,
        lon,
        tuple(site["bbox"]),
        observed=site["observed"],
        index=site["index"],
        sources=sources,
        tried=tried,
    ):
        if stop.is_set():
            return {**rec, "verdict": "not_checked", "reason": "the check ran out of time"}, None
        box = _at_least(site["bbox"], lat, lon, S2_MIN_M) if cand.gsd_m > 2 else site["bbox"]
        try:
            jpeg = sharp.read(cand, tuple(box))
            img = cand
            break
        except Exception as e:  # noqa: BLE001 - no data there, storage down: next candidate
            tried.append(f"read {cand.source}: {_clean(sharp.redact(str(e)), 120)}")
    if img is None or jpeg is None:
        return {**rec, "verdict": "no_image", "reason": "No open image of this site to check"}, None
    rec.update(
        bbox=box,
        source=img.source,
        gsd_m=round(img.gsd_m, 2),
        date=img.date,
        licence=_clean(img.licence, TEXT_MAX),
        credit=_clean(img.credit, TEXT_MAX),
    )
    if stop.is_set():
        return {**rec, "verdict": "not_checked", "reason": "the check ran out of time"}, None
    model_id = cfg["models"][key]["id"]
    text = prompts.load(
        "harness/visual_check_site",
        request=_fence(request),
        claim=_fence(site["claim"]),
        credit=_fence(rec["credit"]),
        gsd=rec["gsd_m"],
        date=_fence(img.date or "unknown"),
    )
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [{"image": {"format": "jpeg", "source": {"bytes": jpeg}}}, {"text": text}],
        }
    ]
    usage = {"input_tokens": 0, "output_tokens": 0}
    try:
        for attempt in range(2):
            reply, u, _ = _converse(client, model_id, prompts.load("harness/visual_check"), messages)
            for k in usage:
                usage[k] += u[k]
            try:
                verdict, reason = parse(reply)
                break
            except ValueError as e:
                if attempt:
                    raise
                messages += [
                    {"role": "assistant", "content": [{"text": reply or "(empty)"}]},
                    {
                        "role": "user",
                        "content": [{"text": prompts.load("harness/visual_check_retry", error=e)}],
                    },
                ]
    except Exception as e:  # noqa: BLE001 - Bedrock error or a second bad reply: checked again on re-judge
        rec.update(usage=usage, cost_usd=_cost(cfg, key, usage), model=key, model_id=model_id)
        return {
            **rec,
            "verdict": "error",
            "reason": _clean(sharp.redact(f"{type(e).__name__}: {e}"), REASON_MAX),
        }, None
    rec.update(
        verdict=verdict,
        reason=reason,
        usage=usage,
        cost_usd=_cost(cfg, key, usage),
        model=key,
        model_id=model_id,
    )
    return rec, jpeg


def _lock(run_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(run_id, threading.Lock())


def ensure(cfg: Any, run: Run, client: Any = None) -> dict[str, Any]:
    """Check the run's reported sites, reusing earlier final verdicts; write the archive once."""
    with _lock(run.run_id):
        return _ensure(cfg, run, client)


def _ensure(cfg: Any, run: Run, client: Any) -> dict[str, Any]:
    s = settings(cfg)
    key_json = f"runs/{run.run_id}/visual.json"
    previous = load(run) or {}
    earlier = {x.get("site_id"): x for x in previous.get("sites") or [] if x.get("verdict") in FINAL}
    t0 = time.monotonic()
    out: dict[str, Any] = {
        "schema_version": 1,
        "status": "checked",
        "reason": None,
        "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    found = sites(run, int(s["max_sites"]), float(s["window_m"]))
    todo = [x for x in found if x["site_id"] not in earlier]
    key = checker(cfg, run, list(s["models"]))
    results: dict[str, tuple[dict[str, Any], bytes | None]] = {}
    if key is None and todo:
        # Keep earlier verdicts; only the sites still to check wait for an eligible model.
        out["reason"] = "no eligible checker model"
        for x in todo:
            results[x["site_id"]] = (
                {**x, "verdict": "not_checked", "reason": "no eligible checker model"},
                None,
            )
    if todo and key is not None:
        if client is None:
            from harness.judge import _bedrock

            client = _bedrock(cfg)
        request = run.prompt or ""
        stop = threading.Event()
        pool = ThreadPoolExecutor(max_workers=WORKERS)
        futures = {
            pool.submit(_check_one, cfg, client, key, request, x, list(s["sources"]), stop): x for x in todo
        }
        done, pending = wait(futures, timeout=float(s["deadline_s"]))
        stop.set()
        for f in pending:
            f.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        for f, x in futures.items():
            if f in done and f.exception() is None:
                results[x["site_id"]] = f.result()
            elif f in done:
                results[x["site_id"]] = (
                    {
                        **x,
                        "verdict": "error",
                        "reason": _clean(f"{type(f.exception()).__name__}", REASON_MAX),
                    },
                    None,
                )
            else:
                results[x["site_id"]] = (
                    {**x, "verdict": "not_checked", "reason": "the check ran out of time"},
                    None,
                )
    records = []
    try:
        for n, x in enumerate(found, start=1):
            if x["site_id"] in earlier:
                rec = dict(earlier[x["site_id"]])
            else:
                rec, jpeg = results[x["site_id"]]
                rec = {k: v for k, v in rec.items() if k not in ("observed", "index")}
                if jpeg:
                    image_key = f"runs/{run.run_id}/visual/{x['site_id']}.jpg"
                    run.store.write_bytes(image_key, jpeg)
                    rec["image_key"] = image_key
            rec["n"] = n
            records.append(rec)
        usage = {"input_tokens": 0, "output_tokens": 0}
        for r in records:
            for k in usage:
                usage[k] += int((r.get("usage") or {}).get(k, 0))
        costs = [r["cost_usd"] for r in records if isinstance(r.get("cost_usd"), int | float)]
        fresh = [rec for rec, _ in results.values()]
        new = [float(r["cost_usd"]) for r in fresh if isinstance(r.get("cost_usd"), int | float)]
        if not any(r.get("verdict") in FINAL for r in records) and out["reason"]:
            out["status"] = "not_checked"
        out.update(
            sites=records,
            usage=usage,
            cost_usd=round(sum(costs), 6) if costs else None,  # every recorded check, reused ones included
            new_cost_usd=round(sum(new), 6),  # the calls this judgement made
            elapsed_s=round(time.monotonic() - t0, 1),
        )
        run.store.write_text(key_json, json.dumps(out, indent=1))
    except Exception as e:  # noqa: BLE001 - archive unwritable: the criterion is N/A, re-judge retries
        # The earlier visual.json (if any) is left as it was: its final verdicts stay scored and reusable.
        log.warning("visual check archive write failed: %s", type(e).__name__)
        return {
            **out,
            "status": "error",
            "reason": f"archive write failed: {type(e).__name__}",
            "sites": records,
        }
    return out
