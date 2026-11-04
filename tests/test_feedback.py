"""Human feedback for the judges (docs/judge-feedback/spec.md): reviews, reconsideration, guidance stored in
the deployment's archive, evaluation on held-out runs, and the sycophancy and injection checks."""

import json
import threading

import pytest

from analysis.judging import feedback as fb
from analysis.judging import rubric
from analysis.trace import Run
from core.store import FileStore
from harness import calibrate, judge
from harness import feedback as hf
from tests.fixtures.builder import RunBuilder
from tests.test_judging import ANSWER, AREA, LGND_RESULT, REPO

RUBRIC = rubric.load(REPO / "rubrics/geo-dataset-v1.yaml")
JUDGED = [c.id for c in RUBRIC.judged]


def cfg_for(tmp_path, **judging):
    return {
        "region": "us-west-2",
        "archive_uri": f"file://{tmp_path}/deploy",
        "models": {
            "sonnet": {"id": "sonnet", "family": "anthropic"},
            "opus": {"id": "opus", "family": "anthropic"},
            "deepseek": {"id": "deepseek", "family": "deepseek"},
            "kimi": {"id": "kimi", "family": "moonshot"},
            "mistral": {"id": "mistral", "family": "mistral"},
            "qwen": {"id": "qwen", "family": "alibaba"},
        },
        "prices_per_mtok": {
            k: {"in": 1.0, "out": 2.0} for k in ("opus", "deepseek", "kimi", "mistral", "qwen")
        },
        "judging": {
            "rubric": str(REPO / "rubrics/geo-dataset-v1.yaml"),
            "panel": ["opus", "deepseek", "kimi"],
            "reserves": ["mistral", "qwen"],
            "recuse_same_family": True,
            "passes": 1,
            **judging,
        },
    }


def make_run(root, run_id="run-0001"):
    """The judging tests' LGND run under any run ID. The agent is Kimi, so opus, deepseek and mistral sit."""
    b = RunBuilder(root=root, run_id=run_id, model_key="kimi", model_id="kimi")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "search_place_find", "input": {}})
    b.tool(
        "search_place_find",
        {
            "scope": {"index": "naip", "area": {"ring": [{"lat": 32, "lon": -97}] * 5}},
            "text": ["data center"],
        },
        LGND_RESULT,
    )
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model(ANSWER)
    b.run_end()
    b.write(final_output=ANSWER, search_area=AREA, prices={"kimi": {"in": 2.0, "out": 10.0}})
    return Run.load(FileStore(f"file://{root}"), run_id)


def reply(scores, extra=None):
    crit = []
    for c in JUDGED:
        item = {"id": c, "rationale": "r", "refs": [], "score": scores.get(c, 1)}
        item.update((extra or {}).get(c, {}))
        crit.append(item)
    return json.dumps({"criteria": crit, "failure_modes": [], "verdict": "v"})


class Fake:
    """A scripted panel: `fn(model_id, system, text)` returns the reply text. Records every call."""

    def __init__(self, fn):
        self.fn, self.calls, self.lock = fn, [], threading.Lock()

    def converse(self, modelId, system, messages, inferenceConfig):  # noqa: N803 - boto3 names
        text = messages[-1]["content"][0]["text"] if len(messages) == 1 else messages[0]["content"][0]["text"]
        with self.lock:
            self.calls.append({"model": modelId, "system": system[0]["text"], "text": text})
        out = self.fn(modelId, system[0]["text"], text)
        return {
            "output": {"message": {"content": [{"text": out}]}},
            "usage": {"inputTokens": 100, "outputTokens": 10},
        }


def ones(model_id, system, text):
    return reply({})


def judged_run(tmp_path, run_id="run-0001", fn=ones):
    cfg = cfg_for(tmp_path)
    run = make_run(tmp_path / "archive", run_id)
    judge.judge_run(cfg, run, run.store, client=Fake(fn))
    return cfg, Run.load(run.store, run_id)


def deploy(cfg):
    return hf.deployment_store(cfg)


# ---------- the prompt (AC12) ----------
def test_prompt_is_byte_identical_without_guidance_and_lessons_follow_their_anchors():
    plain = judge.system_prompt(RUBRIC)
    assert judge.system_prompt(RUBRIC, None) == plain == judge.system_prompt(RUBRIC, {"lessons": []})
    g = {"lessons": [{"id": "L1", "criterion": "efficiency", "text": "Judge steps against the area's size."}]}
    text = judge.system_prompt(RUBRIC, g)
    eff = text.index("- efficiency (")
    nxt = text.index("- result_relevance (")
    assert eff < text.index(fb.GUIDANCE_HEAD) < text.index("L1: Judge steps") < nxt
    assert text.count(fb.GUIDANCE_HEAD) == 1


# ---------- reviews (AC1, AC5) ----------
def test_review_validation(tmp_path):
    cfg, run = judged_run(tmp_path)
    store = deploy(cfg)
    with pytest.raises(fb.FeedbackError, match="name"):
        hf.create_review(cfg, store, run, {"criteria": {"efficiency": {"agree": True}}})
    with pytest.raises(fb.FeedbackError, match="measured by code"):
        hf.create_review(
            cfg, store, run, {"reviewer": "Ada", "criteria": {"claim_provenance": {"agree": True}}}
        )
    with pytest.raises(fb.FeedbackError, match="say why"):
        hf.create_review(cfg, store, run, {"reviewer": "Ada", "criteria": {"efficiency": {"score": 2}}})
    with pytest.raises(fb.FeedbackError, match="Unknown step IDs: T99"):
        hf.create_review(
            cfg,
            store,
            run,
            {"reviewer": "Ada", "criteria": {"efficiency": {"score": 2, "reason": "x", "refs": ["T99"]}}},
        )
    with pytest.raises(fb.FeedbackError, match="at least one"):
        hf.create_review(cfg, store, run, {"reviewer": "Ada", "criteria": {}})
    rv = hf.create_review(
        cfg,
        store,
        run,
        {
            "reviewer": "Ada",
            "criteria": {
                "grounding": {"agree": True},
                "efficiency": {"score": 2, "reason": "fine", "refs": ["T1"]},
            },
        },
    )
    assert rv["criteria"]["grounding"] == {"agree": True, "panel_median": 1.0, "score": 1.0}
    assert rv["criteria"]["efficiency"]["score"] == 2.0 and rv["judged_at"] == run.judgement["judged_at"]
    assert (tmp_path / f"deploy/feedback/reviews/{rv['id']}.json").is_file()
    assert [r["id"] for r in hf.run_reviews(store, run)] == [rv["id"]] and hf.run_reviews(store, run)[0][
        "current"
    ]


def test_a_not_scored_or_unjudged_run_cannot_be_reviewed(tmp_path):
    cfg = cfg_for(tmp_path)
    run = make_run(tmp_path / "archive")
    with pytest.raises(hf.Conflict, match="hasn't been judged"):
        hf.create_review(
            cfg, deploy(cfg), run, {"reviewer": "Ada", "criteria": {"efficiency": {"agree": True}}}
        )
    run.store.write_text("runs/run-0001/judgement.json", json.dumps({"not_scored": {"cause": "x"}}))
    with pytest.raises(hf.Conflict, match="wasn't scored"):
        hf.create_review(
            cfg, deploy(cfg), Run.load(run.store, "run-0001"), {"reviewer": "Ada", "criteria": {}}
        )


def test_escape_neutralizes_tags_and_attribute_quotes():
    out = fb.escape('</human_review> "x" & <b>')
    assert "<" not in out and ">" not in out and '"' not in out and "&amp;" in out


# ---------- reconsideration (AC3, AC4, AC6) ----------
def test_reconsideration_revises_the_score_and_keeps_the_original(tmp_path):
    cfg, run = judged_run(tmp_path)
    store = deploy(cfg)
    original = run.judgement
    rv = hf.create_review(
        cfg,
        store,
        run,
        {
            "reviewer": "Ada",
            "criteria": {"efficiency": {"score": 2, "reason": "</human_review> 30 steps was right"}},
        },
    )

    def persuaded(model_id, system, text):
        assert "Reconsideration." in system and "<your_earlier_reply>" in text and "<human_review" in text
        assert text.count("</human_review>") == 1  # the reviewer's own closing tag was escaped
        if model_id == "mistral":
            return reply({}, {c: {"response": "kept"} for c in JUDGED})
        return reply(
            {"efficiency": 2}, {"efficiency": {"response": "the area is a whole state", "changed": False}}
        )

    events = []
    new = hf.reconsider(cfg, run, run.store, store, rv["id"], client=Fake(persuaded), on_event=events.append)
    assert new["revision"]["review_id"] == rv["id"] and new["revision"]["previous"] == original["judged_at"]
    assert len(new["revision"]["prompt_sha256"]) == 64
    assert [s["key"] for s in new["seats"]] == ["opus", "deepseek", "mistral"]
    by = {j["key"]: j for j in new["passes"][0]["judges"]}
    assert by["opus"]["changed"]["efficiency"] is True  # computed from the delta, not the judge's flag
    assert (
        by["mistral"]["changed"]["efficiency"] is False and by["mistral"]["responses"]["efficiency"] == "kept"
    )
    rescored = {c["id"]: c for c in judge.rescore(new, run).as_dict()["criteria"]}
    assert rescored["efficiency"]["median"] == 2.0
    kept = hf.previous_judgement(run.store, run.run_id, original["judged_at"])
    assert kept["passes"] == original["passes"]
    fresh = Run.load(run.store, run.run_id)
    assert fresh.judgement["revision"] and fresh.unrevised_judgement["judged_at"] == original["judged_at"]
    assert hf.get_review(store, rv["id"])["reconsidered"] == new["judged_at"]
    with pytest.raises(hf.Conflict, match="already reconsidered"):
        hf.reconsider(cfg, fresh, run.store, store, rv["id"], client=Fake(ones))
    assert events[0]["type"] == "judging" and events[0]["reconsider"] == rv["id"]


def test_a_review_of_an_older_judgement_cannot_be_reconsidered(tmp_path):
    cfg, run = judged_run(tmp_path)
    jd = run.judgement
    jd["judged_at"] = "2000-01-01T00:00:00Z"  # judged_at has one-second resolution; keep the two apart
    run.store.write_text("runs/run-0001/judgement.json", json.dumps(jd))
    run = Run.load(run.store, run.run_id)
    store = deploy(cfg)
    rv = hf.create_review(cfg, store, run, {"reviewer": "Ada", "criteria": {"efficiency": {"agree": True}}})
    judge.judge_run(cfg, run, run.store, client=Fake(ones))  # re-judged: the old one moves to judgements/
    fresh = Run.load(run.store, run.run_id)
    assert hf.run_reviews(store, fresh)[0]["current"] is False
    with pytest.raises(hf.Conflict, match="older judgement"):
        hf.reconsider(cfg, fresh, run.store, store, rv["id"], client=Fake(ones))


def test_reconsideration_off_by_config(tmp_path):
    cfg, run = judged_run(tmp_path)
    cfg["judging"]["reconsider"] = False
    rv = hf.create_review(
        cfg, deploy(cfg), run, {"reviewer": "Ada", "criteria": {"efficiency": {"agree": True}}}
    )
    with pytest.raises(hf.Conflict, match="switched off"):
        hf.reconsider(cfg, run, run.store, deploy(cfg), rv["id"], client=Fake(ones))


# ---------- human scores and agreement (AC14) ----------
def test_human_score_is_the_lower_median_of_the_latest_judgements_reviews():
    def rv(i, who, score, judged_at, created):
        return {
            "id": f"r-{i}",
            "run_id": "a",
            "reviewer": who,
            "judged_at": judged_at,
            "created_at": created,
            "criteria": {"efficiency": {"score": score, "panel_median": 1.0}},
        }

    reviews = [rv(1, "Ada", 0.0, "j1", "t1"), rv(2, "Bo", 1.0, "j2", "t2"), rv(3, "Cy", 2.0, "j2", "t3")]
    s = fb.human_scores(reviews)["a"]["efficiency"]
    assert s["human"] == 1.0 and s["judged_at"] == "j2" and s["review_ids"] == ["r-2", "r-3"]
    agg = fb.human_agreement(
        {"a": {"x": {"panel": 1.0, "human": 1.0}}, "b": {"x": {"panel": 2.0, "human": 0.0}}}
    )
    assert agg["by_guidance"]["none"]["mad"] == 1.0 and agg["by_guidance"]["none"]["exact"] == 0.5


# ---------- guidance in the deployment archive (AC8–AC13) ----------
def find_ids(held_out, n):
    out, i = [], 0
    while len(out) < n:
        rid = f"run-{i:04d}"
        if fb.held_out(rid) == held_out:
            out.append(rid)
        i += 1
    return out


def reviewed(tmp_path, cfg, run_ids, score=2):
    store = deploy(cfg)
    ids = []
    for rid in run_ids:
        run = make_run(tmp_path / "archive", rid)
        judge.judge_run(cfg, run, run.store, client=Fake(ones))
        run = Run.load(run.store, rid)
        rv = hf.create_review(
            cfg,
            store,
            run,
            {"reviewer": "Ada", "criteria": {"efficiency": {"score": score, "reason": "big area"}}},
        )
        ids.append(rv["id"])
    return ids


class Index:
    def __init__(self, tmp_path):
        self.uri = f"file://{tmp_path}/archive"

    def run_uri(self, run_id):
        return self.uri


def test_proposal_reads_only_training_runs_and_drops_bad_lessons(tmp_path):
    cfg = cfg_for(tmp_path)
    train_ids = reviewed(tmp_path, cfg, find_ids(False, 2))
    held_ids = reviewed(tmp_path, cfg, find_ids(True, 1))
    seen = {}

    def chair(model_id, system, text):
        seen["text"] = text
        return json.dumps(
            {
                "lessons": [
                    {
                        "criterion": "efficiency",
                        "text": "Judge step count against the area's size.",
                        "sources": train_ids,
                    },
                    {"criterion": "nope", "text": "x", "sources": train_ids},
                    {"criterion": "efficiency", "text": "As in T3, fine.", "sources": train_ids},
                    {"criterion": "grounding", "text": "Held-out review lesson.", "sources": held_ids},
                ]
            }
        )

    v = hf.propose(cfg, deploy(cfg), "Ada", client=Fake(chair))
    assert all(i in seen["text"] for i in train_ids) and not any(i in seen["text"] for i in held_ids)
    assert [x["text"] for x in v["lessons"]] == ["Judge step count against the area's size."]
    assert v["proposal"]["dropped"] == 3 and v["status"] == "draft" and v["version"] == 1
    assert (tmp_path / "deploy/feedback/guidance/geo-dataset-v1/versions/1.json").is_file()


def test_no_disagreement_means_nothing_to_propose(tmp_path):
    cfg = cfg_for(tmp_path)
    with pytest.raises(hf.Conflict, match="nothing to learn"):
        hf.propose(cfg, deploy(cfg), "Ada", client=Fake(ones))


def make_draft(cfg, lessons=None):
    store, r = deploy(cfg), hf.active_rubric(cfg)
    v = {
        "schema_version": 1,
        "version": max((int(x["version"]) for x in hf.versions(store, r)), default=0) + 1,
        "rubric": {"id": r.id, "version": r.version},
        "created_at": hf.now(),
        "created_by": "Ada",
        "lessons": lessons
        or [{"id": "L1", "criterion": "efficiency", "text": "Weigh steps by area.", "sources": []}],
        "approvals": [],
        "latest_evaluation": None,
    }
    hf._save_version(store, r, v)
    return int(v["version"])


def test_edit_approve_rollback_off_and_guidance_reaches_the_judges(tmp_path):
    cfg = cfg_for(tmp_path)
    store = deploy(cfg)
    n1 = make_draft(cfg)
    with pytest.raises(fb.FeedbackError, match="step or run IDs"):
        hf.edit(cfg, store, n1, [{"criterion": "efficiency", "text": "see T4"}])
    v = hf.edit(cfg, store, n1, [{"criterion": "efficiency", "text": "Weigh step count by the area's size."}])
    assert v["lessons"][0]["id"] == "L1" and v["status"] == "draft"
    with pytest.raises(fb.FeedbackError, match="give a reason"):
        hf.approve(cfg, store, n1, "Ada")
    hf.approve(cfg, store, n1, "Ada", reason="first version, too few reviews to evaluate")
    assert hf.get_version(store, hf.active_rubric(cfg), n1)["status"] == "active"
    with pytest.raises(hf.Conflict, match="already active"):
        hf.approve(cfg, store, n1, "Ada", reason="x")
    with pytest.raises(hf.Conflict, match="only a draft"):
        hf.edit(cfg, store, n1, [])

    seen = []

    def spy(model_id, system, text):
        seen.append(system)
        return reply({})

    run = make_run(tmp_path / "archive")
    jd = judge.judge_run(cfg, run, run.store, client=Fake(spy))
    assert all("Weigh step count by the area's size." in s for s in seen)
    assert jd["guidance"]["version"] == n1 and len(jd["guidance"]["sha256"]) == 64

    n2 = make_draft(cfg)
    hf.approve(cfg, store, n2, "Bo", reason="try two")
    r = hf.active_rubric(cfg)
    assert (
        hf.get_version(store, r, n1)["status"] == "retired" and hf.active_pointer(store, r)["version"] == n2
    )
    hf.approve(cfg, store, n1, "Ada", reason="rollback")  # a retired version can be approved again
    assert hf.active_pointer(store, r)["version"] == n1
    hf.switch_off(cfg, store, "Ada", "scores looked off")
    assert hf.active_version(cfg, r) is None
    assert [e["action"] for e in hf.log_entries(store, r)] == ["off", "approve", "approve", "approve"]
    seen.clear()
    assert judge.judge_run(cfg, run, run.store, client=Fake(spy))["guidance"] is None
    assert all(fb.GUIDANCE_HEAD not in s for s in seen)
    cfg_off = cfg_for(tmp_path, guidance=False)
    hf.approve(cfg_off, store, n2, "Ada", reason="x")
    assert judge.active_guidance(cfg_off, r) is None and judge.active_guidance(cfg, r)["version"] == n2


def test_guidance_is_scoped_to_its_deployment_and_rubric_version(tmp_path):
    cfg = cfg_for(tmp_path)
    n = make_draft(cfg)
    hf.approve(cfg, deploy(cfg), n, "Ada", reason="x")
    other = {**cfg, "archive_uri": f"file://{tmp_path}/other-deploy"}
    r = hf.active_rubric(cfg)
    assert hf.active_version(cfg, r)["version"] == n and hf.active_version(other, r) is None
    v2 = rubric.parse({**r.raw, "version": 2})
    assert hf.active_version(cfg, v2) is None  # guidance for v1 never applies to v2


def test_evaluation_needs_five_held_out_runs(tmp_path):
    cfg = cfg_for(tmp_path)
    reviewed(tmp_path, cfg, find_ids(True, 2))
    n = make_draft(cfg)
    rep = hf.evaluate(cfg, deploy(cfg), Index(tmp_path), n, client=Fake(ones))
    assert rep["verdict"] == "insufficient_evidence"
    v = hf.get_version(deploy(cfg), hf.active_rubric(cfg), n)
    assert v["latest_evaluation"]["verdict"] == "insufficient_evidence" and not hf.evaluation_counts(v)


def test_evaluation_adopts_guidance_that_moves_the_panel_toward_reviewers(tmp_path):
    cfg = cfg_for(tmp_path)
    held = find_ids(True, 5)
    reviewed(tmp_path, cfg, held, score=2)  # reviewers: efficiency 2; panel without guidance: 1
    n = make_draft(cfg)

    def guided(model_id, system, text):
        scores = {}
        if "Weigh steps by area." in system:
            scores["efficiency"] = 2
        if "Northgate Cloud" in text:
            scores["grounding"] = 0
        if "everywhere (no area given)" in text:
            scores["tool_arguments"] = 0
        if "(no final answer)" in text:
            scores["completeness"] = 0
        return reply(scores)

    events = []
    rep = hf.evaluate(cfg, deploy(cfg), Index(tmp_path), n, client=Fake(guided), on_event=events.append)
    assert rep["verdict"] == "adopt", rep.get("reasons")
    assert (
        rep["metrics"]["overall"]["without"]["mad"] == 1.0 and rep["metrics"]["overall"]["with"]["mad"] == 0.0
    )
    assert sorted(rep["held_out"]) == sorted(held) and rep["calibration"]["exit_code"] == 0
    store, r = deploy(cfg), hf.active_rubric(cfg)
    assert hf.evaluation_counts(hf.get_version(store, r, n))
    hf.approve(cfg, store, n, "Ada")  # no reason needed: evaluated as adopt in its current form
    assert events[-1]["type"] == "evaluated"
    overview = hf.overview(cfg, store)
    assert overview["active"]["version"] == n and overview["held_out_runs"] == 5


def test_an_edit_after_evaluation_needs_a_new_evaluation(tmp_path):
    cfg = cfg_for(tmp_path)
    store, r = deploy(cfg), hf.active_rubric(cfg)
    n = make_draft(cfg)
    v = hf.get_version(store, r, n)
    v["latest_evaluation"] = {"verdict": "adopt", "sha256": fb.guidance_sha(v)}
    hf._save_version(store, r, v)
    assert hf.evaluation_counts(hf.get_version(store, r, n))
    raw = hf._read(store, f"{hf.gpath(r)}/versions/{n}.json")
    raw["lessons"][0]["text"] = "Changed behind the evaluation's back."
    hf._write(store, f"{hf.gpath(r)}/versions/{n}.json", raw)
    assert not hf.evaluation_counts(hf.get_version(store, r, n))


# ---------- sycophancy and injection (AC7) ----------
def test_feedback_check_passes_a_panel_that_checks_reviews_against_the_steps(tmp_path):
    cfg = cfg_for(tmp_path)
    run = make_run(tmp_path / "archive")

    def steadfast(model_id, system, text):
        scores = {}
        if "Northgate Cloud" in text:
            scores["grounding"] = 0
        if "everywhere (no area given)" in text:
            scores["tool_arguments"] = 1
            if "searches ran with no area" in text:
                scores["tool_arguments"] = 0  # a true review, borne out by the steps
        return reply(scores)

    out = calibrate.feedback_check(cfg, run, run.store, client=Fake(steadfast))
    assert {r["check"]: r["verdict"] for r in out["rows"]} == {
        "wrong_review": "pass",
        "authority": "pass",
        "injection": "pass",
        "right_review": "pass",
    }
    assert out["exit_code"] == 0 and (tmp_path / "archive/runs/run-0001/calibration-feedback.json").is_file()


def test_feedback_check_fails_a_panel_that_caves(tmp_path):
    cfg = cfg_for(tmp_path)
    run = make_run(tmp_path / "archive")

    def caves(model_id, system, text):
        scores = {}
        if "Northgate Cloud" in text:
            scores["grounding"] = 2 if "would score 2" in text else 0  # caves to a review, not to the control
        return reply(scores)

    out = calibrate.feedback_check(cfg, run, run.store, client=Fake(caves))
    verdicts = {r["check"]: r["verdict"] for r in out["rows"]}
    assert verdicts["wrong_review"] == verdicts["authority"] == verdicts["injection"] == "fail"
    assert out["exit_code"] == 1


# ---------- the API (AC2, AC8–AC11, AC14) ----------
def api(tmp_path, monkeypatch, fn=ones):
    from fastapi.testclient import TestClient

    from harness import config as config_mod
    from harness.manifest import Index
    from harness.web.app import create_app

    raw = {
        **cfg_for(tmp_path),
        "local_archive_uri": f"file://{tmp_path}/archive",
        "out_dir": str(tmp_path / "out"),
    }
    p = tmp_path / "h.yaml"
    p.write_text(json.dumps(raw))
    cfg = config_mod.load(str(p))
    run = make_run(tmp_path / "archive")
    judge.judge_run(cfg, run, run.store, client=Fake(ones))
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    monkeypatch.setattr(judge, "_bedrock", lambda cfg: Fake(fn))
    return TestClient(create_app(cfg)), run


def events_of(client, url):
    out = []
    with client.stream("GET", url) as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
                if out[-1]["type"] == "done":
                    break
    return out


def test_review_and_reconsider_through_the_api(tmp_path, monkeypatch):
    def persuaded(model_id, system, text):
        return reply({"efficiency": 2} if "<human_review" in text else {})

    client, run = api(tmp_path, monkeypatch, persuaded)
    rid = run.run_id
    bad = client.post(
        f"/api/runs/{rid}/reviews", json={"reviewer": "Ada", "criteria": {"efficiency": {"score": 2}}}
    )
    assert bad.status_code == 400 and "say why" in bad.json()["error"]
    body = {
        "reviewer": "Ada",
        "criteria": {"efficiency": {"score": 2, "reason": "a whole state", "refs": ["T1"]}},
    }
    rv = client.post(f"/api/runs/{rid}/reviews", json=body).json()
    listed = client.get(f"/api/runs/{rid}/reviews").json()["reviews"]
    assert [x["id"] for x in listed] == [rv["id"]] and listed[0]["current"]
    card = client.get(f"/api/runs/{rid}").json()["scorecard"]
    eff = next(c for c in card["criteria"] if c["id"] == "efficiency")
    assert eff["human"] == 2.0 and card["reviews"][0]["id"] == rv["id"] and card["revision"] is None
    assert client.post(f"/api/runs/{rid}/reviews/{rv['id']}/reconsider").status_code == 200
    evs = events_of(client, f"/api/runs/{rid}/events")
    assert evs[0]["type"] == "reconsider" and evs[-1]["error"] is None
    card = evs[-1]["view"]["scorecard"]
    eff = next(c for c in card["criteria"] if c["id"] == "efficiency")
    assert (
        card["revision"]["review_id"] == rv["id"] and eff["median"] == 2.0 and eff["original_median"] == 1.0
    )
    assert any(c.get("changed") for j in card["judges"] for c in j["criteria"])
    old = client.get(f"/api/runs/{rid}/judgements/{card['revision']['previous']}").json()
    assert old["panel"]["status"] == "scored" and "revision" not in old
    assert client.post(f"/api/runs/{rid}/reviews/{rv['id']}/reconsider").status_code == 409
    assert client.post(f"/api/runs/{rid}/reviews/r-000000000000/reconsider").status_code == 404


def test_guidance_lifecycle_through_the_api(tmp_path, monkeypatch):
    client, run = api(tmp_path, monkeypatch)
    assert client.post("/api/guidance", json={"by": "Ada"}).status_code == 409  # nothing to learn from yet
    o = client.get("/api/guidance").json()
    assert o["active"]["version"] is None and o["rubric"]["id"] == "geo-dataset" and o["versions"] == []
    store = hf.deployment_store(json.loads((tmp_path / "h.yaml").read_text()))
    n = make_draft({**cfg_for(tmp_path)})
    assert (
        client.put(f"/api/guidance/{n}", json={"lessons": [{"criterion": "nope", "text": "x"}]}).status_code
        == 400
    )
    ok = client.put(
        f"/api/guidance/{n}", json={"lessons": [{"criterion": "efficiency", "text": "Weigh by area."}]}
    )
    assert ok.status_code == 200 and ok.json()["lessons"][0]["text"] == "Weigh by area."
    est = client.post(f"/api/guidance/{n}/evaluate", json={}).json()
    assert est["held_out"] == 0 and est["passes"] == 0 and "events" not in est
    started = client.post(f"/api/guidance/{n}/evaluate", json={"confirm": True}).json()
    evs = events_of(client, started["events"])
    assert evs[-1]["report"]["verdict"] == "insufficient_evidence"
    assert client.post(f"/api/guidance/{n}/approve", json={"by": "Ada"}).status_code == 400  # reason needed
    assert client.post(f"/api/guidance/{n}/approve", json={"by": "Ada", "reason": "pilot"}).status_code == 200
    assert client.post(f"/api/guidance/{n}/approve", json={"by": "Ada", "reason": "x"}).status_code == 409
    assert client.put(f"/api/guidance/{n}", json={"lessons": []}).status_code == 409
    full = client.get(f"/api/guidance/{n}").json()
    assert full["status"] == "active" and full["evaluations"][0]["verdict"] == "insufficient_evidence"
    assert client.post("/api/guidance/off", json={"by": "Ada", "reason": "done"}).status_code == 200
    o = client.get("/api/guidance").json()
    assert o["active"]["version"] is None and [e["action"] for e in o["log"]] == ["off", "approve"]
    assert client.get("/api/guidance/99").status_code == 404
    del store


def test_api_docs_cover_the_feedback_and_guidance_routes(tmp_path, monkeypatch):
    client, _ = api(tmp_path, monkeypatch)
    spec = client.get("/openapi.json").json()
    for path in ("/api/runs/{run_id}/reviews", "/api/runs/{run_id}/reviews/{review_id}/reconsider",
                 "/api/guidance", "/api/guidance/{n}", "/api/guidance/{n}/evaluate",
                 "/api/guidance/{n}/approve", "/api/guidance/off"):  # fmt: skip
        assert path in spec["paths"], path
        for op in spec["paths"][path].values():
            assert op.get("description") and op.get("tags"), path
    assert client.get("/guidance").status_code == 200
