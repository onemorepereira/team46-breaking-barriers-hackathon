"""`run_view`: the one JSON shape the console renders for a run, built from the archive alone (replayable)."""

from __future__ import annotations

from typing import Any

from analysis import provenance, signals, summary, timeline
from analysis.judging import measure
from analysis.trace import Run
from core import geometry
from harness import imagery, judge


def _bbox_polygon(b: list[float]) -> dict[str, Any]:
    w, s, e, n = (float(x) for x in b)
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def map_layers(m: measure.Measured) -> dict[str, Any]:
    chips, claims = [], []
    for x in m.located:
        props = {
            "ref": x.ref,
            "node": x.node,
            "inside": x.inside,
            "label": x.label,
            "observed": x.observed,
            "similarity": x.similarity,
            "index": x.index,
            "claim": x.claim,
            "lat": x.lat,
            "lon": x.lon,
        }
        if x.source == "chip" and x.bbox:
            props["tile_url"] = imagery.tile_url(x.index, x.bbox)
            props["tile_source"] = imagery.ATTRIBUTION.get(x.index or "", imagery.ATTRIBUTION["s2"])
            chips.append({"type": "Feature", "geometry": _bbox_polygon(x.bbox), "properties": props})
        elif x.source == "claim":
            claims.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [x.lon, x.lat]},
                    "properties": props,
                }
            )
    area = None
    if m.area_geometry:
        area = {"type": "Feature", "geometry": m.area_geometry, "properties": {"label": m.area_label}}
    return {
        "area": area,
        "chips": {"type": "FeatureCollection", "features": chips},
        "claims": {"type": "FeatureCollection", "features": claims},
    }


def scorecard(run: Run) -> dict[str, Any] | None:
    jd = run.judgement
    if not jd:
        return None
    result = judge.rescore(jd, run).as_dict()
    anchors = {c["id"]: c.get("anchors", {}) for c in jd["rubric"]["snapshot"].get("criteria", [])}
    top = max(jd["rubric"]["snapshot"].get("scale") or [2])
    judges = []
    for j in (jd.get("passes") or [{}])[0].get("judges", []):
        scores = j.get("scores") or {}
        judges.append(
            {
                "key": j["key"],
                "model_id": j["model_id"],
                "family": j["family"],
                "status": j["status"],
                "recused_for": j.get("recused_for"),
                "error": j.get("error"),
                "cost_usd": j.get("cost_usd"),
                "latency_s": j.get("latency_s"),
                "verdict": j.get("verdict"),
                "failure_modes": j.get("failure_modes", []),
                "score": round(sum(scores.values()) / len(scores) / top * 100, 1) if scores else None,
                "criteria": [
                    {
                        "id": cid,
                        "score": s,
                        "rationale": (j.get("rationales") or {}).get(cid, ""),
                        "refs": (j.get("refs") or {}).get(cid, []),
                    }
                    for cid, s in scores.items()
                ],
            }
        )
    return {
        **result,
        "judges": judges,
        "anchors": anchors,
        "rubric": {k: jd["rubric"][k] for k in ("id", "version")},
        "rubric_title": jd["rubric"]["snapshot"].get("title"),
        "judged_at": jd.get("judged_at"),
        "judging_cost_usd": jd.get("judging_cost_usd"),
        "seats": jd.get("seats", []),
    }


def run_view(run: Run) -> dict[str, Any]:
    prov = provenance.grade(run)
    m = measure.measure(run, prov)
    sig = signals.compute(run)
    summ = summary.build(run, prov)
    card = scorecard(run)
    entries = [e.as_dict() for e in timeline.entries(run.spans)]
    by_ref: dict[str, list[float]] = {}
    for x in m.located:
        if x.ref and x.bbox:
            b = by_ref.setdefault(x.ref, [180.0, 90.0, -180.0, -90.0])
            west, south, east, north = x.bbox
            by_ref[x.ref] = [min(b[0], west), min(b[1], south), max(b[2], east), max(b[3], north)]
    for e in entries:
        e["bounds"] = by_ref.get(e["ref"])
        e["results"] = sum(1 for x in m.located if x.source == "chip" and x.ref == e["ref"])
    snap = run.manifest.get("snapshot") or {}
    kpis = {
        "score": card["overall"] if card else None,
        "verdict": card["verdict"] if card else "not scored" if run.not_scored else "not judged",
        "not_scored_cause": (run.not_scored or {}).get("cause"),
        "confidence": card["confidence"] if card else None,
        "confidence_reasons": card["confidence_reasons"] if card else [],
        "workflow": card["dimensions"]["workflow"] if card else None,
        "output": card["dimensions"]["output"] if card else None,
        "agent_cost_usd": sig.estimated_cost_usd,
        "judging_cost_usd": card["judging_cost_usd"] if card else None,
        "tool_calls": sig.tool_calls,
        "errors": sig.errors,
        "retries": sig.retries,
        "repeats": sig.repeats,
        "model_calls": sig.model_calls,
        "tokens_in": sig.input_tokens,
        "tokens_out": sig.output_tokens,
        "runtime_s": sig.runtime_s,
        "claims_matched": m.claims_matched,
        "claims_total": m.claims_total,
        "claims_block_missing": m.claims_block_missing,
        "claims_inside": m.claims_inside,
        "claims_located": m.claims_located,
        "chips_inside": m.chips_inside,
        "chips_total": m.chips_total,
        "within_one": card["within_one"] if card else None,
        "mad": card["mad"] if card else None,
        "valid_judges": card["valid_judges"] if card else None,
        "trace_integrity": m.trace_integrity,
        "missing_fields": m.missing_fields,
    }
    # Claims are located in the same order provenance graded them; match by position, not by name.
    located_claims = iter([x for x in m.located if x.source == "claim"])
    claims = []
    for c in prov.claims:
        inside = None
        if geometry.coordinate_pair(c.value):
            inside = next(located_claims).inside
        claims.append(
            {"claim": c.claim, "value": c.value, "ref": c.ref, "status": c.status, "inside": inside,
             "value_class": c.value_class}
        )  # fmt: skip
    return {
        "run": {
            "id": run.run_id,
            "model_key": run.manifest.get("model_key"),
            "model_id": run.manifest.get("model_id"),
            "status": run.status,
            "backend": run.manifest.get("backend"),
            "started_at": run.manifest.get("started_at"),
            "prompt": run.prompt,
            "prompt_file": run.manifest.get("prompt_file"),
            "area": (snap.get("search_area") or {}).get("label"),
            "area_source": (snap.get("search_area") or {}).get("source"),
            "area_mode": (snap.get("search_area") or {}).get("mode"),
        },
        "kpis": kpis,
        "timeline": entries,
        "map": map_layers(m),
        "scorecard": card,
        "claims": claims,
        "final_answer": measure.answer_text(run.final_output),
        "narrative": summ.narrative,
        "trouble_spots": [t.__dict__ for t in summ.trouble_spots],
        "datasets": signals.datasets_accessed(run),
    }


def run_row(run: Run) -> dict[str, Any]:
    """One row of the runs table."""
    sig = signals.compute(run)
    jd = run.judgement
    p = judge.rescore(jd, run) if jd else None
    prompt = run.prompt
    return {
        "id": run.run_id,
        "started_at": run.manifest.get("started_at"),
        "model_key": run.manifest.get("model_key"),
        "status": run.status,
        "prompt": " ".join(prompt.split())[:140],
        "prompt_file": run.manifest.get("prompt_file"),
        "score": p.overall if p else None,
        "verdict": p.verdict if p else "not scored" if run.not_scored else "not judged",
        "not_scored_cause": (run.not_scored or {}).get("cause"),
        "confidence": p.confidence if p else None,
        "cost_usd": sig.estimated_cost_usd,
        "judging_cost_usd": jd.get("judging_cost_usd") if jd else None,
        "tool_calls": sig.tool_calls,
        "errors": sig.errors,
        "runtime_s": sig.runtime_s,
        "area": ((run.manifest.get("snapshot") or {}).get("search_area") or {}).get("label"),
    }
