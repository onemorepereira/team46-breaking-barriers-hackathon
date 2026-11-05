"""`run_view`: the one JSON shape the console renders for a run, built from the archive alone (replayable)."""

from __future__ import annotations

import json
from typing import Any

from analysis import provenance, signals, summary, timeline
from analysis.judging import measure, rubric
from analysis.judging.explain import explain
from analysis.trace import Run
from core import geometry
from harness import imagery, judge


def _bbox_polygon(b: list[float]) -> dict[str, Any]:
    w, s, e, n = (float(x) for x in b)
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def map_layers(m: measure.Measured, run_id: str | None = None, serve_tiles: bool = True) -> dict[str, Any]:
    """GeoJSON for the map. Result tiles load through the console's /tiles/chip endpoint (docs/tile-cache),
    or straight from the provider when `tiles.serve` is off."""
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
            props["tile_url"] = (
                imagery.console_chip_url(x.index, x.bbox, run_id)
                if serve_tiles
                else imagery.tile_url(x.index, x.bbox)
            )
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


def scorecard(
    run: Run,
    deploy_store: Any = None,
    reconsider: bool = True,
    rubric_path: str | None = None,
    result: Any = None,
    measured: Any = None,
) -> dict[str, Any] | None:
    jd = run.judgement
    if not jd:
        return None
    result = (result if result is not None else judge.rescore(jd, run)).as_dict()
    names = rubric.display_names(rubric.parse(jd["rubric"]["snapshot"]), rubric_path)
    for c in result["criteria"]:
        c["plain"] = names[c["id"]]
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
                "stood_in_for": j.get("stood_in_for"),
                "error": j.get("error"),
                "cost_usd": j.get("cost_usd"),
                "latency_s": j.get("latency_s"),
                "temperature": j.get("temperature", 0),  # None: the model rejected temperature 0
                "verdict": j.get("verdict"),
                "failure_modes": j.get("failure_modes", []),
                "score": round(sum(scores.values()) / len(scores) / top * 100, 1) if scores else None,
                "criteria": [
                    {
                        "id": cid,
                        "score": s,
                        "rationale": (j.get("rationales") or {}).get(cid, ""),
                        "refs": (j.get("refs") or {}).get(cid, []),
                        "changed": (j.get("changed") or {}).get(cid),
                        "response": (j.get("responses") or {}).get(cid),
                    }
                    for cid, s in scores.items()
                ],
            }
        )
    return {
        **result,
        **pass_stability(jd, run, measured if measured is not None else measure.measure(run)),
        "judges": judges,
        "anchors": anchors,
        "rubric": {k: jd["rubric"][k] for k in ("id", "version")},
        "rubric_title": jd["rubric"]["snapshot"].get("title"),
        "judged_at": jd.get("judged_at"),
        "judging_cost_usd": jd.get("judging_cost_usd"),
        "seats": jd.get("seats", []),
        **review_layer(run, jd, result, deploy_store, reconsider),
    }


def pass_stability(jd: dict[str, Any], run: Run, measured: Any) -> dict[str, Any]:
    """How settled the score is (docs/judging-stability): every judge's vote on every criterion across all
    passes, and the spread of the per-pass scores. `overall_range` is the lowest and highest score a single
    pass gave; `overall_se` the standard error of the headline (sd of pass scores / sqrt(passes))."""
    passes = [p for p in jd.get("passes") or [] if p.get("judges")]
    votes: dict[str, dict[str, list[int]]] = {}
    for p in passes:
        for j in p["judges"]:
            if j.get("status") != "ok":
                continue
            for cid, v in (j.get("scores") or {}).items():
                votes.setdefault(cid, {}).setdefault(j["key"], []).append(int(v))
    singles = [
        x for p in passes if (x := judge.rescore({**jd, "passes": [p]}, run, measured).overall) is not None
    ]
    se = None
    if len(singles) > 1:
        mean = sum(singles) / len(singles)
        sd = (sum((x - mean) ** 2 for x in singles) / (len(singles) - 1)) ** 0.5
        se = round(sd / len(singles) ** 0.5, 1)
    return {
        "votes_all": votes,
        "pass_count": len(passes),
        "overall_range": [min(singles), max(singles)] if singles else None,
        "overall_se": se,
        "passes_dropped": jd.get("dropped_slow_passes", 0),
    }


def review_layer(
    run: Run, jd: dict[str, Any], result: dict[str, Any], deploy_store: Any, reconsider: bool = True
) -> dict[str, Any]:
    """Human feedback on the scorecard (docs/judge-feedback AC4): the revision, each criterion's original
    median and human score, the run's reviews, and the guidance the judgement used."""
    from analysis.judging import feedback as fb
    from analysis.judging.rubric import parse
    from harness import feedback

    out: dict[str, Any] = {
        "revision": jd.get("revision"),
        "guidance": None,
        "guidance_error": jd.get("guidance_error"),
        "reviews": [],
        "reconsider_enabled": reconsider,
    }
    g = jd.get("guidance")
    if g:
        out["guidance"] = {"version": g.get("version"), "lessons": g.get("snapshot") or []}
    r = parse(jd["rubric"]["snapshot"])
    original: dict[str, float] = {}
    if jd.get("revision"):
        prev = feedback.previous_judgement(run.store, run.run_id, str(jd["revision"].get("previous") or ""))
        original = fb.panel_medians(prev, r) if prev else {}
    reviews: list[dict[str, Any]] = []
    if deploy_store is not None:
        try:
            reviews = feedback.run_reviews(deploy_store, run)
        except Exception:  # noqa: BLE001 - the scorecard stands without reviews
            reviews = []
    human = fb.human_scores(reviews).get(run.run_id, {}) if reviews else {}
    for c in result.get("criteria", []):
        if c.get("kind") != "judged":
            continue
        c["original_median"] = original.get(c["id"]) if jd.get("revision") else None
        h = human.get(c["id"])
        c["human"] = h["human"] if h else None
        c["human_reviewers"] = h["reviewers"] if h else []
    out["reviews"] = reviews
    return out


def run_view(
    run: Run,
    serve_tiles: bool = True,
    deploy_store: Any = None,
    reconsider: bool = True,
    rubric_path: str | None = None,
    narrative_model: str | None = None,
) -> dict[str, Any]:
    from analysis import report as report_mod
    from harness import reference as reference_mod

    prov = provenance.grade(run)
    m = measure.measure(run, prov)
    tie = run.store.read_text(f"runs/{run.run_id}/reference/tie.json")
    ref = report_mod.reference_of(
        run, m, prov, reference_mod.repo_sha(json.loads(tie).get("id")) if tie else None
    )  # docs/adb-alignment AC4: scored from the run's own archived snapshot
    lic = report_mod.licences_of(run, ref, narrative_model)
    sig = signals.compute(run)
    summ = summary.build(run, prov)
    result = judge.rescore(run.judgement, run, m) if run.judgement else None
    card = scorecard(run, deploy_store, reconsider, rubric_path, result=result, measured=m)
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
        "presentable": lic["presentable"],
        "licence_blockers": lic["blockers"],
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
        "map": map_layers(m, run.run_id, serve_tiles),
        "scorecard": card,
        "conditions": m.conditions,
        "explanation": explain(run, result, measured=m),
        "source_check_note": provenance.matcher_update_note(run.judgement),
        "claims": claims,
        "final_answer": measure.answer_text(run.final_output),
        "narrative": summ.narrative,
        "trouble_spots": [t.__dict__ for t in summ.trouble_spots],
        "datasets": signals.datasets_accessed(run),
        "reference": ref,
        "licences": lic,
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
