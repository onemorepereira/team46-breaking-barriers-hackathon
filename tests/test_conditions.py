"""Condition evidence, archival extraction, scoring and legacy replay."""

import json

import pytest

from analysis import report
from analysis.judging import conditions, dossier, measure, panel
from core.geometry import distance_km
from harness.conditions import ensure, validate
from harness.web.view import run_view
from tests.test_explain import judged
from tests.test_judging import RUBRIC, lgnd_run

ITEMS = [
    {"id": "C1", "kind": "target", "text": "data centers"},
    {"id": "C2", "kind": "inside_area", "text": "inside Testville"},
    {
        "id": "C3",
        "kind": "within_distance",
        "text": "within 10 miles of a protected natural area",
        "distance_km": 16.09344,
        "reference_feature": "protected natural area",
    },
]


def save(run, items=ITEMS, **extra):
    run.store.write_text(f"runs/{run.run_id}/conditions.json", json.dumps({"conditions": items, **extra}))


def test_distance_known_pairs_and_dateline():
    assert distance_km(0, 0, 0, 1) == pytest.approx(111.195, abs=0.01)
    assert distance_km(10, 20, 10, 20) == 0
    assert distance_km(0, 179, 0, -179) == pytest.approx(222.39, abs=0.01)


def test_missing_reference_is_unverified_and_outside_area_is_contradicted(tmp_path):
    run = lgnd_run(tmp_path)
    save(run)
    m = conditions.evaluate(run)
    assert m["rows"][0]["cells"][1]["status"] == "supported"
    assert m["rows"][1]["cells"][1]["status"] == "contradicted"
    assert all(r["cells"][2]["status"] == "unverified" for r in m["rows"])
    assert m["score"] == 0.25 and m["needs_review"]
    assert "No located" in m["rows"][0]["cells"][2]["reason"]
    assert measure.measure(run).condition_compliance == 0.25
    run, result = judged(run)
    assert result.confidence == "Medium"
    assert result.dimensions["output"] <= 25
    assert result.overall <= 62.5
    assert run_view(run)["conditions"]["rows"]
    assert "unverified" in report.render_run(report.analyze(run), "now")
    assert "Conditions in the request" in dossier.render(dossier.build(run))


def test_reference_must_have_the_right_type_and_coordinates(tmp_path):
    run = lgnd_run(tmp_path)
    save(run)
    s = run.tool_results[0]
    uri = s.attr("harness.tool.result_uri")
    for label, lat, expected in [
        ("office building", 32.5, "unverified"),
        ("protected natural area", 32.51, "supported"),
        ("protected natural area", 50, "unverified"),
    ]:
        data = {"lat": lat, "lon": -96.5, "name": label}
        run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))
        # Claims still need their own coordinate evidence in the same successful result.
        data["sites"] = [{"lat": 32.5, "lon": -96.5}, {"lat": 34, "lon": -96.5}]
        run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))
        cell = conditions.evaluate(run)["rows"][0]["cells"][2]
        assert cell["status"] == expected
        if expected == "supported":
            assert cell["refs"] == ["T1", "T1"]
        if lat == 50:
            assert "nearer feature is absent" in cell["reason"]


def test_legacy_runs_are_not_extracted_or_scored(tmp_path, socket_disabled):
    run = lgnd_run(tmp_path)
    assert conditions.evaluate(run) is None
    assert measure.measure(run).condition_compliance is None
    assert run_view(run)["conditions"] is None
    old = {
        **RUBRIC.raw,
        "version": 1,
        "criteria": [c for c in RUBRIC.raw["criteria"] if c["id"] != "condition_compliance"],
    }
    from analysis.judging.rubric import parse

    result = panel.aggregate(parse(old), [], measure.measure(run))
    assert not any(c.id == "condition_compliance" for c in result.criteria)


def test_extraction_is_once_and_failure_is_visible(tmp_path):
    run = lgnd_run(tmp_path)

    class Fake:
        calls = 0

        def converse(self, **kw):
            self.calls += 1
            return {"output": {"message": {"content": [{"text": json.dumps({"conditions": ITEMS})}]}}}

    fake = Fake()
    cfg = {"narrative_model": "m", "models": {"m": {"id": "fake"}}, "region": "us-west-2"}
    ensure(cfg, run, fake)
    ensure(cfg, run, fake)
    assert fake.calls == 1 and conditions.load(run)["conditions"][2]["distance_km"] == 16.09344
    other = lgnd_run(tmp_path / "bad")
    ensure({}, other)
    assert conditions.load(other)["status"] == "not_checked"
    assert conditions.evaluate(other)["status"] == "not_checked"
    assert not measure.measure(other).conditions_need_review


@pytest.mark.parametrize("km", [0, -1, float("inf"), True])
def test_bad_distance_is_rejected(km):
    with pytest.raises(ValueError):
        validate(
            {
                "conditions": [
                    {
                        "kind": "within_distance",
                        "text": "near park",
                        "distance_km": km,
                        "reference_feature": "park",
                    }
                ]
            }
        )


def test_extraction_failure_prevents_an_overall_score(tmp_path):
    run = lgnd_run(tmp_path)
    save(run, [], error="Service unavailable")
    run, result = judged(run)
    assert result.overall is None and result.verdict == "not scored"
    assert "incomplete" in run_view(run)["explanation"]["headline"]


def test_omitted_distance_condition_is_an_extraction_error(tmp_path):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = "Find data centers within 10 miles of a protected area in Testville"

    class Fake:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": json.dumps({"conditions": [ITEMS[0]]})}]}}}

    ensure({"narrative_model": "m", "models": {"m": {"id": "fake"}}, "region": "us-west-2"}, run, Fake())
    assert conditions.load(run)["error"]


def test_negative_reference_labels_do_not_supply_distance_evidence(tmp_path):
    run = lgnd_run(tmp_path)
    save(run)
    uri = run.tool_results[0].attr("harness.tool.result_uri")
    data = {
        "lat": 32.5,
        "lon": -96.5,
        "name": "not a protected natural area",
        "sites": [{"lat": 34, "lon": -96.5}],
    }
    run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))
    assert conditions.evaluate(run)["rows"][0]["cells"][2]["status"] == "unverified"


def test_distance_request_without_locations_cannot_get_high_output_score(tmp_path):
    run = lgnd_run(tmp_path, final_output="Here is a plan to find sites.")
    save(run)
    run, result = judged(run)
    assert result.dimensions["output"] == 0
    assert result.confidence != "High"


CFG = {"narrative_model": "m", "models": {"m": {"id": "fake"}}, "region": "us-west-2"}


class Replies:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.calls = []

    def converse(self, **kwargs):
        import copy

        self.calls.append(copy.deepcopy(kwargs))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return {"output": {"message": {"content": [{"text": reply}]}}, "usage": {"inputTokens": 5}}


@pytest.mark.parametrize("wrapper", ["```json\n%s\n```", "Here are the conditions: %s Done."])
def test_extraction_accepts_wrapped_json(tmp_path, wrapper):
    run = lgnd_run(tmp_path)
    fake = Replies(wrapper % json.dumps({"conditions": ITEMS}))
    ensure(CFG, run, fake)
    assert conditions.load(run)["conditions"] == ITEMS
    assert "error" not in conditions.load(run)


def test_invalid_reply_retries_with_hint_and_records_all_usage(tmp_path):
    run = lgnd_run(tmp_path)
    fake = Replies('{"conditions":[null]}', json.dumps({"conditions": ITEMS}))
    ensure(CFG, run, fake)
    assert conditions.load(run)["usage"]["inputTokens"] == 10
    assert "condition must be an object" in fake.calls[1]["messages"][-1]["content"][0]["text"]
    assert conditions.load(run)["attempts"] == 2


def test_temporary_failure_can_be_retried_and_success_cached(tmp_path):
    run = lgnd_run(tmp_path)
    fake = Replies(TimeoutError(), json.dumps({"conditions": ITEMS}))
    ensure(CFG, run, fake)
    assert conditions.load(run)["error"]
    ensure(CFG, run, fake)
    ensure(CFG, run, fake)
    assert len(fake.calls) == 2
    assert "error" not in conditions.load(run)


@pytest.mark.parametrize("prompt", ["solar farms larger than 2 km²", "find sites using 10 km tiles"])
def test_area_and_resolution_are_not_proximity(tmp_path, prompt):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = prompt
    ensure(CFG, run, Replies(json.dumps({"conditions": [ITEMS[0]]})))
    assert "error" not in conditions.load(run)


def test_missing_model_does_not_unscore_and_can_be_enabled_later(tmp_path):
    run = lgnd_run(tmp_path)
    ensure({}, run)
    run, result = judged(run)
    assert result.overall is not None
    criterion = next(c for c in result.criteria if c.id == "condition_compliance")
    assert criterion.score is None and criterion.value == "not checked"
    assert result.confidence == "Medium"
    explanation = run_view(run)["explanation"]
    assert "not checked" in explanation["summary"]
    assert any("narrative_model" in c for c in explanation["check_by_hand"])
    ensure(CFG, run, Replies(json.dumps({"conditions": ITEMS})))
    assert conditions.load(run)["conditions"]


@pytest.mark.parametrize("error", [None, "temporary failure"])
def test_rubric_without_conditions_is_not_capped_or_unscored(tmp_path, error):
    from analysis.judging.rubric import parse

    run = lgnd_run(tmp_path)
    run, _ = judged(run)
    old = {**RUBRIC.raw, "criteria": [c for c in RUBRIC.raw["criteria"] if c["id"] != "condition_compliance"]}
    baseline = panel.aggregate(parse(old), run.judgement["passes"], measure.measure(run))
    save(run, **({"error": error} if error else {}))
    result = panel.aggregate(parse(old), run.judgement["passes"], measure.measure(run))
    assert result.as_dict() == baseline.as_dict()


@pytest.mark.parametrize(
    "record",
    [
        {"Lat": 32.51, "Lng": -96.5, "Name": "protected natural area"},
        {
            "type": "Feature",
            "properties": {"name": "protected natural area"},
            "geometry": {"type": "Point", "coordinates": [-96.5, 32.51]},
        },
        {"type": "Point", "coordinates": [-96.5, 32.51], "name": "protected natural area"},
    ],
)
def test_reference_coordinate_aliases_and_geojson(tmp_path, record):
    run = lgnd_run(tmp_path)
    save(run)
    uri = run.tool_results[0].attr("harness.tool.result_uri")
    data = {"reference": record, "sites": [{"lat": 32.5, "lon": -96.5}]}
    run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))
    assert conditions.evaluate(run)["rows"][0]["cells"][2]["status"] == "supported"


def test_claim_site_cannot_be_its_own_reference(tmp_path):
    run = lgnd_run(tmp_path)
    save(run)
    uri = run.tool_results[0].attr("harness.tool.result_uri")
    data = {"lat": 32.5, "lng": -96.5, "description": "data center bordering a protected natural area"}
    run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))
    assert conditions.evaluate(run)["rows"][0]["cells"][2]["status"] == "unverified"


def test_run_view_and_static_report_grade_provenance_once(tmp_path, monkeypatch, socket_disabled):
    from analysis import provenance

    run = lgnd_run(tmp_path)
    save(run)
    run, _ = judged(run)
    original = provenance.grade
    calls = []

    def counted(run):
        calls.append(run.run_id)
        return original(run)

    monkeypatch.setattr(provenance, "grade", counted)
    run_view(run)
    assert len(calls) == 1
    calls.clear()
    report.render_run(report.analyze(run), "now")
    assert len(calls) == 1


def test_explicit_judging_retries_conditions_before_building_dossier(tmp_path, monkeypatch):
    from harness import judge
    from tests.test_judging import CFG as JUDGE_CFG

    run = lgnd_run(tmp_path)
    save(run, [], error="timeout")
    cfg = JUDGE_CFG
    events = []
    monkeypatch.setattr("harness.conditions.ensure", lambda *a: events.append("ensure"))

    def stop(*args):
        events.append("dossier")
        raise RuntimeError("stop before model call")

    monkeypatch.setattr(judge.dossier_mod, "build", stop)
    with pytest.raises(RuntimeError, match="stop before model call"):
        judge.judge_run(cfg, run, run.store)
    assert events == ["ensure", "dossier"]


def test_condition_review_survives_three_other_evidence_gaps(tmp_path, monkeypatch):
    from dataclasses import replace
    from importlib import import_module

    module = import_module("analysis.judging.explain")
    run = lgnd_run(tmp_path)
    save(run)
    run, result = judged(run)
    measured = replace(measure.measure(run), claims_matched=0)
    monkeypatch.setattr(module, "_image_checks", lambda run: (1, 1))
    checks = module.explain(run, result, measured=measured)["check_by_hand"]
    assert len(checks) == 3
    assert checks[0].startswith("Review each unverified or contradicted condition")


def test_two_bad_replies_remain_visible_until_explicit_retry(tmp_path, socket_disabled):
    run = lgnd_run(tmp_path)
    fake = Replies("not json", "still not json")
    ensure(CFG, run, fake)
    assert len(fake.calls) == 2
    assert conditions.load(run)["error"]
    run, result = judged(run)
    assert result.overall is None
    # Offline replay must neither retry the failed extraction nor change its archive.
    before = run.store.read_text(f"runs/{run.run_id}/conditions.json")
    run_view(run)
    assert run.store.read_text(f"runs/{run.run_id}/conditions.json") == before


# ---------- second review pass ----------
LABEL = "data center bordering a protected natural area"
REFERENCE = "protected natural area"


def _result_with(run, data):
    uri = run.tool_results[0].attr("harness.tool.result_uri")
    run.store.write_text(f"runs/{run.run_id}/{uri}", json.dumps(data))


def _claims(*values):
    claims = [{"claim": f"site {i}", "value": v, "ref": "T1"} for i, v in enumerate(values)]
    return "Sites.\n```json\n" + json.dumps({"claims": claims}) + "\n```"


def _distance_cell(run):
    return conditions.evaluate(run)["rows"][0]["cells"][2]


def _square(lat, lon, half=0.05):
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
    ]
    return [[*ring, ring[0]]]


def test_site_cannot_be_its_own_reference_when_its_coordinates_are_rounded(tmp_path):
    run = lgnd_run(tmp_path, final_output=_claims("32.9001, -96.7003"))
    save(run)
    _result_with(run, {"lat": 32.90012, "lon": -96.70034, "name": LABEL})
    assert _distance_cell(run)["status"] == "unverified"


def test_another_claimed_site_cannot_be_the_reference(tmp_path):
    run = lgnd_run(tmp_path, final_output=_claims("32.5, -96.5", "32.6, -96.5"))
    save(run)
    sites = [{"lat": 32.5, "lon": -96.5, "name": LABEL}, {"lat": 32.6, "lon": -96.5, "name": LABEL}]
    _result_with(run, {"sites": sites})
    assert all(r["cells"][2]["status"] == "unverified" for r in conditions.evaluate(run)["rows"])


def test_real_reference_close_to_a_coarsely_rounded_claim_still_counts(tmp_path):
    run = lgnd_run(tmp_path, final_output=_claims("32.5, -96.5"))
    save(run)
    reference = {"lat": 32.51, "lon": -96.5, "name": REFERENCE}
    _result_with(run, {"sites": [{"lat": 32.5, "lon": -96.5}], "reference": reference})
    assert _distance_cell(run)["status"] == "supported"


@pytest.mark.parametrize(
    "record",
    [
        {
            "type": "Feature",
            "properties": {"name": REFERENCE},
            "geometry": {"type": "Polygon", "coordinates": _square(32.6, -96.5)},
        },
        {
            "type": "Feature",
            "properties": {"name": REFERENCE},
            "geometry": {"type": "MultiPolygon", "coordinates": [_square(32.6, -96.5)]},
        },
        {"name": REFERENCE, "centroid": {"lat": 32.6, "lon": -96.5}},
        {"name": REFERENCE, "geometry": {"type": "Point", "coordinates": [-96.5, 32.6]}},
    ],
)
def test_polygon_and_nested_centroid_references_count(tmp_path, record):
    run = lgnd_run(tmp_path, final_output=_claims("32.5, -96.5"))
    save(run)
    _result_with(run, {"reference": record, "sites": [{"lat": 32.5, "lon": -96.5}]})
    assert _distance_cell(run)["status"] == "supported"


def test_site_inside_a_large_polygon_reference_is_supported(tmp_path):
    run = lgnd_run(tmp_path, final_output=_claims("32.5, -96.5"))
    save(run)
    record = {"type": "Polygon", "name": REFERENCE, "coordinates": _square(32.5, -96.5, half=2)}
    _result_with(run, {"reference": record, "sites": [{"lat": 32.5, "lon": -96.5}]})
    cell = _distance_cell(run)
    assert cell["status"] == "supported" and "0.00 km" in cell["reason"]


def test_malformed_polygon_reference_is_ignored(tmp_path):
    run = lgnd_run(tmp_path, final_output=_claims("32.5, -96.5"))
    save(run)
    record = {"type": "Polygon", "name": REFERENCE, "coordinates": [["x"], 3]}
    _result_with(run, {"reference": record, "sites": [{"lat": 32.5, "lon": -96.5}]})
    assert _distance_cell(run)["status"] == "unverified"


def test_cap_uses_the_weakest_condition_not_the_pooled_share(tmp_path):
    run = lgnd_run(tmp_path)
    save(run)
    m = measure.measure(run)
    assert m.condition_compliance == 0.25 and m.condition_cap == 0.0
    run, result = judged(run)
    assert result.dimensions["output"] == 0
    assert next(c for c in result.criteria if c.id == "condition_compliance").score == 25


def test_none_found_scores_zero_and_asks_for_a_hand_check(tmp_path):
    run = lgnd_run(tmp_path, final_output="I searched thoroughly; no sites qualify.")
    save(run)
    run, result = judged(run)
    assert result.dimensions["output"] == 0
    assert next(c for c in result.criteria if c.id == "condition_compliance").value == "no locations listed"
    text = run_view(run)["explanation"]
    assert "listed no locations" in text["summary"]
    assert text["check_by_hand"][0].startswith("If none found")


def test_empty_conditions_are_valid_and_cached(tmp_path):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = "Tell me about data centers"
    fake = Replies(json.dumps({"conditions": []}))
    ensure(CFG, run, fake)
    ensure(CFG, run, fake)
    assert len(fake.calls) == 1
    assert "error" not in conditions.load(run)
    run, result = judged(run)
    assert result.overall is not None and result.verdict == "scored"
    assert next(c for c in result.criteria if c.id == "condition_compliance").value == "not applicable"
    assert run_view(run)["conditions"]["rows"] == []


@pytest.mark.parametrize("prompt", ["", "   "])
def test_blank_prompt_is_not_sent_or_failed(tmp_path, prompt):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = prompt
    fake = Replies()
    ensure(CFG, run, fake)
    assert not fake.calls and "error" not in conditions.load(run)


@pytest.mark.parametrize(
    "prompt",
    [
        "sites within a 10-mile radius of a park",
        "sites 10 miles from a river",
        "sites within 10 mi of a park",
        "sites closer than 5 km to a lake",
        "sites under 5 km from a lake",
        "sites within about 10 kilometres of a park",
    ],
)
def test_proximity_phrasings_are_caught_when_omitted(tmp_path, prompt):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = prompt
    only_target = json.dumps({"conditions": [ITEMS[0]]})
    ensure(CFG, run, Replies(only_target, only_target))
    assert conditions.load(run)["error"]


@pytest.mark.parametrize(
    "prompt",
    [
        "sites at least 5 km from a school",
        "sites more than 10 miles from a river",
        "corridors with 10 km of road",
    ],
)
def test_other_distances_are_not_proximity(tmp_path, prompt):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = prompt
    ensure(CFG, run, Replies(json.dumps({"conditions": [ITEMS[0]]})))
    assert "error" not in conditions.load(run)


def test_every_stated_proximity_limit_must_be_extracted(tmp_path):
    run = lgnd_run(tmp_path)
    run.__dict__["prompt"] = "sites within 10 miles of a park and within 5 km of a river"
    one = json.dumps({"conditions": [ITEMS[2]]})
    ensure(CFG, run, Replies(one, one))
    assert conditions.load(run)["error"]
    restated = lgnd_run(tmp_path / "again")
    restated.__dict__["prompt"] = "sites within 10 miles of a park. Only sites within 10 miles of a park."
    ensure(CFG, restated, Replies(one))
    assert "error" not in conditions.load(restated)


@pytest.mark.parametrize(
    "text",
    [
        "{truncated",
        "[]",
        '"text"',
        '{"conditions": "x"}',
        '{"conditions": [{"kind": "target"}]}',
        '{"conditions": [{"id": "C1", "kind": "within_distance", "text": "near"}]}',
    ],
)
def test_damaged_file_keeps_the_run_page_open_and_re_judge_replaces_it(tmp_path, text):
    run = lgnd_run(tmp_path)
    run.store.write_text(f"runs/{run.run_id}/conditions.json", text)
    run, result = judged(run)
    assert result.overall is None and result.verdict == "not scored"
    view = run_view(run)
    assert "incomplete" in view["explanation"]["headline"]
    assert "Re-judge" in " ".join(view["explanation"]["check_by_hand"])
    assert "Conditions in the request" in dossier.render(dossier.build(run))
    assert report.render_run(report.analyze(run), "now")
    ensure(CFG, run, Replies(json.dumps({"conditions": ITEMS})))
    assert "error" not in conditions.load(run)


def test_recovery_step_survives_three_evidence_gaps(tmp_path, monkeypatch):
    from dataclasses import replace
    from importlib import import_module

    module = import_module("analysis.judging.explain")
    run = lgnd_run(tmp_path)
    save(run, [], error="timeout")
    run, result = judged(run)
    measured = replace(measure.measure(run), claims_matched=0)
    monkeypatch.setattr(module, "_image_checks", lambda run: (1, 1))
    checks = module.explain(run, result, measured=measured)["check_by_hand"]
    assert len(checks) == 3
    assert any("Re-judge" in c for c in checks)


def test_disagreement_doubt_depends_on_the_actual_confidence_reasons(tmp_path):
    from analysis.judging.explain import explain

    run = lgnd_run(tmp_path)
    save(run)
    run, result = judged(run, medium=True)
    assert "judges disagree" in explain(run, result)["summary"]
    only_gap = lgnd_run(tmp_path / "gap")
    save(only_gap)
    only_gap, result = judged(only_gap)
    assert result.confidence == "Medium"
    assert "judges disagree" not in explain(only_gap, result)["summary"]


def test_doubt_is_explained_under_a_rubric_without_conditions(tmp_path):
    from analysis.judging.explain import explain
    from analysis.judging.rubric import parse

    run = lgnd_run(tmp_path)
    save(run)
    run, _ = judged(run, medium=True)
    old = {**RUBRIC.raw, "criteria": [c for c in RUBRIC.raw["criteria"] if c["id"] != "condition_compliance"]}
    result = panel.aggregate(parse(old), run.judgement["passes"], measure.measure(run))
    assert result.confidence == "Medium"
    assert "judges disagree" in explain(run, result)["summary"]


def test_report_shows_each_conditions_state(tmp_path):
    run = lgnd_run(tmp_path)
    ensure({}, run)
    assert "were not checked" in report.render_run(report.analyze(run), "now")
    run.store.write_text(f"runs/{run.run_id}/conditions.json", json.dumps({"conditions": []}))
    assert "No checkable conditions" in report.render_run(report.analyze(run), "now")
