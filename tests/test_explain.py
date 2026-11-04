"""User-facing explanations: evidence limits, all result states, replay, and old scorecards."""

import copy
import json
import re

import pytest
from fastapi.testclient import TestClient

from analysis import report
from analysis.judging import panel, rubric
from analysis.judging.explain import explain
from analysis.trace import Run
from core.store import FileStore
from harness.manifest import Index
from harness.web.app import create_app
from harness.web.view import run_view
from tests.fixtures.builder import RunBuilder
from tests.test_judging import RUBRIC, lgnd_run
from tests.test_web import cfg_for


def judged(run, score=2, *, medium=False, old=False):
    snapshot = copy.deepcopy(RUBRIC.raw)
    if old:
        for c in snapshot["criteria"]:
            c.pop("plain", None)
    judges = [
        {"key": key, "family": key, "model_id": key, "status": "ok",
         "scores": {c.id: score for c in RUBRIC.judged}, "rationales": {}, "refs": {},
         "failure_modes": []}
        for key in ("first", "second", "third")
    ]  # fmt: skip
    passes = [{"judges": judges}]
    if medium:
        passes.append({"judges": []})
    record = {"rubric": {"id": RUBRIC.id, "version": 1, "snapshot": snapshot},
              "passes": passes, "seats": []}  # fmt: skip
    run.store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(record))
    run = Run.load(run.store, run.run_id)
    return run, panel.rescore(run.judgement, run)


@pytest.mark.parametrize("medium", [False, True])
def test_scores_agreement_counts_and_limits_are_distinct(tmp_path, medium, socket_disabled):
    run, result = judged(lgnd_run(tmp_path), medium=medium)
    text = explain(run, result)
    assert result.confidence == ("Medium" if medium else "High")
    assert f"{result.overall:g}/100" in text["headline"]
    assert "2 distinct locations" in text["summary"]
    assert "1 of 2 location entries are inside Testville" in text["summary"]
    assert "2 of 2 listed values matched" in text["summary"]
    assert "do not prove the answer is correct" in text["summary"]
    assert "outside the area" in text["check_by_hand"][0]
    assert ("agreement is medium" if medium else "agreement is high") in text["summary"]


@pytest.mark.parametrize(
    "answer,status,reason",
    [("", "success", "without a final answer"), ("A result.", "error", "No tool returned usable data")],
)
def test_failed_runs_explain_why(tmp_path, answer, status, reason):
    run, result = judged(lgnd_run(tmp_path, final_output=answer, tool_status=status))
    text = explain(run, result)
    assert "failed" in text["headline"]
    assert "0/100" in text["summary"] and reason in text["summary"]


def test_infrastructure_and_never_judged_states(tmp_path):
    run = lgnd_run(tmp_path)
    text = explain(run, None)
    assert "not been judged" in text["headline"] and "Re-judge" in text["summary"]
    run.store.write_text(
        f"runs/{run.run_id}/judgement.json",
        json.dumps({"not_scored": {"reason": "infrastructure", "cause": "ExpiredTokenException"}}),
    )
    again = Run.load(run.store, run.run_id)
    text = explain(again, None)
    assert "could not be scored" in text["headline"] and "no score" in text["summary"]
    assert "access and limits" in text["check_by_hand"][-1]
    assert "ExpiredTokenException" not in text["summary"]


def test_missing_judge_replies_and_broken_records(tmp_path):
    run, result = judged(lgnd_run(tmp_path), medium=True)
    result.overall = None
    assert "not enough judge replies" in explain(run, result)["headline"]
    run.manifest["archive_errors"] = 1
    result.overall = 50
    result.confidence = "Low"
    text = explain(run, result)
    assert "saved record" in text["summary"]
    assert any("Restore" in c for c in text["check_by_hand"])


def test_actual_image_verdicts_drive_review_counts_and_later_checks_replace_earlier(tmp_path):
    b = RunBuilder(tmp_path)
    b.run_start()
    b.model("Searching")
    for rows in [[["a", "no"], ["b", "maybe"], ["c", "no"]], [["a", "yes"]]]:
        b.tool(
            "reasoning_imagery_check",
            {},
            json.dumps({"places": {"columns": ["node", "answer"], "rows": rows}}),
        )
        b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model("Three candidates.")
    b.run_end()
    b.write(final_output="Three candidates.")
    run = Run.load(FileStore(f"file://{tmp_path}"), b.run_id)
    text = explain(run, None)
    assert text["check_by_hand"][0] == (
        "Review the 2 image checks that did not confirm a match (1 no, 1 unclear)."
    )
    assert "no listed locations to count" in text["summary"]  # never infer a site count from prose


def test_reasons_are_plain_bounded_and_tied_to_the_saved_result(tmp_path):
    run, result = judged(lgnd_run(tmp_path), score=1)
    result.failure_modes = [{"id": "retry_loop", "votes": 3, "of": 3}]
    text = explain(run, result)
    assert "repeated searches" in text["summary"]
    assert len(text["summary"].split()) <= 120
    assert 1 <= len(text["check_by_hand"]) <= 3
    banned = r"\b(?:criterion|rubric|median|MAD|alpha|dossier|provenance|gate|span|T\d+)\b|[a-z]+_[a-z]+|[α]"
    assert not re.search(banned, " ".join([text["headline"], text["summary"], *text["check_by_hand"]]), re.I)


def test_long_requests_do_not_hide_the_accuracy_limit(tmp_path):
    run, result = judged(lgnd_run(tmp_path))
    run.__dict__["prompt"] = "Find " + "many places " * 200
    text = explain(run, result)
    assert len(text["summary"].split()) <= 120
    assert "do not prove the answer is correct" in text["summary"]


@pytest.mark.parametrize("old", [False, True])
def test_current_plain_labels_work_for_old_and_new_runs_without_changing_scores(tmp_path, old):
    run, result = judged(lgnd_run(tmp_path / "archive"), old=old)
    before = copy.deepcopy(run.judgement)
    current = copy.deepcopy(RUBRIC.raw)
    current["criteria"][0]["plain"] = "Custom current question?"
    custom = tmp_path / "custom.yaml"
    custom.write_text(json.dumps(current))
    view = run_view(run, rubric_path=str(custom))
    assert view["explanation"] == explain(run, result)
    assert view["scorecard"]["criteria"][0]["plain"] == "Custom current question?"
    assert view["kpis"]["score"] == result.overall
    assert run.judgement == before
    html = report.render_run(report.analyze(run, str(custom)), "now")
    assert "What this means" in html and "Custom current question?" in html
    assert html.index("What this means") < html.index("<h2>Run</h2>")


def test_missing_current_labels_fall_back_to_saved_questions(tmp_path):
    raw = copy.deepcopy(RUBRIC.raw)
    for c in raw["criteria"]:
        c.pop("plain", None)
    snapshot = rubric.parse(raw)
    names = rubric.display_names(snapshot, tmp_path / "missing.yaml")
    assert names["grounding"] == snapshot.criteria[5].question
    raw["criteria"][0]["plain"] = []
    with pytest.raises(rubric.RubricError, match="plain"):
        rubric.parse(raw)


def test_api_exposes_plain_explanation_without_network_and_escapes_user_text(tmp_path, monkeypatch):
    import boto3

    def no_aws(*args, **kwargs):
        pytest.fail("displaying a saved explanation must not create an AWS client")

    monkeypatch.setattr(boto3, "client", no_aws)
    cfg = cfg_for(tmp_path)
    run, _ = judged(lgnd_run(tmp_path / "archive"), old=True)
    run.manifest["prompt"] = '<img src=x onerror="alert(1)">'
    run.store.write_text(f"runs/{run.run_id}/run.json", json.dumps(run.manifest))
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    client = TestClient(create_app(cfg))
    data = client.get(f"/api/runs/{run.run_id}").json()
    assert data["explanation"]["headline"]
    assert data["scorecard"]["criteria"][0]["plain"]
    page = client.get(f"/runs/{run.run_id}").text
    assert 'id="explanation-card"' in page
    html = report.render_run(report.analyze(Run.load(run.store, run.run_id)), "now")
    assert "&lt;img" in html and "<img src=x" not in html
