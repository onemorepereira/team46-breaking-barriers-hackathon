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
        ("protected natural area", 32.5, "supported"),
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
    assert conditions.evaluate(other)["error"]
    assert measure.measure(other).conditions_need_review


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
