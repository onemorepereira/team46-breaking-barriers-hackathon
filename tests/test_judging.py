"""Judge panel (docs/judging/spec.md AC1-AC9): rubric, measured criteria, dossier, aggregation, agreement,
confidence, the panel runner (with a fake Bedrock client) and calibration verdicts."""

import json
import threading
from pathlib import Path

import pytest
import yaml

from analysis.judging import alpha, dossier, measure, panel, rubric
from analysis.trace import Run
from core import geometry
from core.store import FileStore
from harness import calibrate, judge
from tests.fixtures.builder import RunBuilder, standard_run

REPO = Path(__file__).resolve().parents[1]
RUBRIC = rubric.load(REPO / "rubrics/geo-dataset-v1.yaml")
JUDGED = [c.id for c in RUBRIC.judged]


# ---------- AC1 rubric ----------
def test_rubric_loads_and_snapshot_round_trips():
    assert len(RUBRIC.judged) == 8 and [c.id for c in RUBRIC.measured] == [
        "claim_provenance",
        "area_compliance",
    ]
    assert RUBRIC.calibration == {
        "unscoped": "tool_arguments",
        "fabricated": "grounding",
        "no_answer": "completeness",
    }
    again = rubric.parse(json.loads(json.dumps(RUBRIC.raw)))  # JSON turns anchor keys into strings
    assert again.sha256 == RUBRIC.sha256 and again.judged[0].anchors[2]


@pytest.mark.parametrize(
    "edit, message",
    [
        (lambda r: r["criteria"][3]["anchors"].pop(2), "criteria[3].anchors: missing 2"),
        (lambda r: r["criteria"][0].update(dimension="vibes"), "criteria[0].dimension"),
        (lambda r: r["criteria"][0].update(kind="guessed"), "criteria[0].kind"),
        (lambda r: r["criteria"][8].update(id="magic_metric"), "no code measures 'magic_metric'"),
        (lambda r: r["calibration"].update(unscoped="claim_provenance"), "rubric.calibration.unscoped"),
        (lambda r: r.pop("scale"), "rubric: missing scale"),
    ],
)
def test_malformed_rubric_is_refused_naming_the_field(edit, message):
    raw = yaml.safe_load((REPO / "rubrics/geo-dataset-v1.yaml").read_text())
    edit(raw)
    with pytest.raises(rubric.RubricError, match=message.replace("[", r"\[").replace("]", r"\]")):
        rubric.parse(raw)


# ---------- AC7 alpha ----------
def test_alpha_matches_krippendorffs_published_example():
    n = None
    data = [
        [1, 2, 3, 3, 2, 1, 4, 1, 2, n, n, n],
        [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, n, 3],
        [n, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, n],
        [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, n],
    ]
    assert round(alpha.alpha(data, "nominal"), 3) == 0.743
    assert round(alpha.alpha(data, "ordinal"), 3) == 0.815
    assert round(alpha.alpha(data, "interval"), 3) == 0.849
    assert alpha.alpha([[2, 2, 2], [2, 2, 2]]) is None  # no variance: undefined, not 1.0


# ---------- fixtures ----------
AREA = {
    "label": "Testville",
    "source": "unit test",
    "mode": "enforce",
    "geometry": {"type": "Polygon", "coordinates": [[[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]]},
}
LGND_RESULT = json.dumps(
    {
        "where": "inside a polygon",
        "matches": {
            "columns": ["node", "lat", "lon", "bbox", "similarity"],
            "rows": [
                ["naip/obs:1", 32.5, -96.5, [-96.51, 32.49, -96.49, 32.51], 0.31],
                ["naip/obs:2", 34.0, -96.5, [-96.51, 33.99, -96.49, 34.01], 0.29],
            ],
        },
    }
)
ANSWER = """Found one data center at 32.5, -96.5.

```json
{"claims": [{"claim": "site 1", "value": "32.5, -96.5", "ref": "T1"},
            {"claim": "site 2", "value": "34.0, -96.5", "ref": "T1"}]}
```"""


def lgnd_run(root, final_output=ANSWER, area=AREA, tool_status="success", model_key="sonnet"):
    b = RunBuilder(root=root, model_key=model_key, model_id="us.anthropic.claude-sonnet-5-5")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "search_place_find", "input": {}})
    b.tool(
        "search_place_find",
        {
            "scope": {"index": "naip", "area": {"ring": [{"lat": 32, "lon": -97}] * 5}},
            "text": ["data center"],
        },
        LGND_RESULT,
        status=tool_status,
    )
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model(final_output)
    b.run_end()
    b.write(final_output=final_output, search_area=area, prices={"sonnet": {"in": 2.0, "out": 10.0}})
    return Run.load(FileStore(f"file://{root}"), "run-0001")


# ---------- AC2 measured ----------
def test_measured_criteria_from_the_archive(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    assert (m.claims_matched, m.claims_total, m.claim_provenance) == (2, 2, 1.0)
    assert (m.claims_inside, m.claims_located, m.area_compliance) == (1, 2, 0.5)  # claims only
    assert (m.chips_inside, m.chips_total, m.search_footprint) == (1, 2, 0.5)  # shown, not scored
    assert m.trace_integrity and m.gates == []


def test_provenance_is_zero_for_prose_without_claims_and_na_without_area(tmp_path):
    m = measure.measure(lgnd_run(tmp_path, final_output="Two sites, trust me.", area=None))
    assert m.claim_provenance == 0.0 and m.area_compliance is None and m.chips_total == 0


def test_fatal_gates(tmp_path):
    m = measure.measure(lgnd_run(tmp_path, final_output='```json\n{"claims": []}\n```', tool_status="error"))
    assert {g["id"] for g in m.gates} == {"no_answer", "no_tool_data"}


# ---------- AC3 dossier ----------
def test_dossier_has_executed_work_only_and_marks_tool_output_untrusted(tmp_path):
    run = lgnd_run(tmp_path)
    d = dossier.build(run)
    text = dossier.render(d)
    assert d.known_refs == {"M1", "T1", "M2"}
    assert '<tool_output ref="T1">' in text and "naip/obs:1" in text
    assert "Find data centers near Dallas" in text  # the task, recovered from the first model call
    assert "Testville" in text and "agent_cost_usd" in text
    assert "claim_provenance" not in text and "area_compliance" not in text  # measured results stay out
    assert text.count("Found one data center") == 1  # the reply appears once, under Final answer


def test_perturbations_plant_one_defect_each(tmp_path):
    d = dossier.build(lgnd_run(tmp_path))
    unscoped = dossier.perturb(d, "unscoped")
    step = next(s for s in unscoped.steps if s.kind == "tool")
    assert "area" not in step.args["scope"] and "everywhere" in step.digest and '"everywhere"' in step.output
    fab = dossier.perturb(d, "fabricated")
    lat, lon = (
        float(x) for x in fab.final_answer.split("Northgate Cloud, at ")[1].split(".\n")[0].split(", ")
    )
    assert geometry.contains(AREA["geometry"], lon, lat)  # inside the area, so it isn't a scope violation
    none = dossier.render(dossier.perturb(d, "no_answer"))
    assert "(no final answer)" in none and "Found one data center" not in none
    assert d.final_answer == ANSWER  # the original is untouched


# ---------- AC5-AC7 aggregation ----------
def judge_reply(key, scores, modes=()):
    return {"key": key, "status": "ok", "scores": scores, "failure_modes": list(modes)}


def passes_with(votes_by_judge, modes=None):
    modes = modes or {}
    return [
        {
            "pass": 1,
            "judges": [
                judge_reply(k, {c: v for c in JUDGED}, modes.get(k, ())) for k, v in votes_by_judge.items()
            ],
        }
    ]


def test_median_dimensions_and_majority_failure_modes(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    p = panel.aggregate(
        RUBRIC,
        passes_with(
            {"a": 2, "b": 2, "c": 1, "d": 0, "e": 2},
            modes={
                "a": ["overconfidence"],
                "b": ["overconfidence"],
                "c": ["overconfidence"],
                "d": ["retry_loop"],
            },
        ),
        m,
    )
    tool = next(c for c in p.criteria if c.id == "tool_selection")
    assert tool.median == 2 and tool.score == 100 and tool.spread == 2 and not tool.unanimous
    area = next(c for c in p.criteria if c.id == "area_compliance")
    assert area.score == 50.0 and area.value == "1/2"
    assert p.dimensions["workflow"] == 100 and p.dimensions["output"] == round((100 * 4 + 100 + 50) / 6, 1)
    assert [f["id"] for f in p.failure_modes] == ["overconfidence"]  # 3 of 5; retry_loop 1 of 5 isn't
    assert p.within_one == 0.0 and p.confidence == "Low"


def test_lower_median_with_four_valid_judges(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    votes = {"a": 2, "b": 2, "c": 1, "d": 1}
    passes = passes_with({**votes})
    passes[0]["judges"].append({"key": "e", "status": "error", "error": "throttled"})  # failed, no stand-in
    p = panel.aggregate(RUBRIC, passes, m)
    assert next(c for c in p.criteria if c.id == "grounding").median == 1  # lower median, an actual vote
    assert p.confidence == "Medium" and "4 of 5 judges valid" in p.confidence_reasons


def test_fatal_gate_fails_the_run_whatever_the_judges_say(tmp_path):
    m = measure.measure(lgnd_run(tmp_path, final_output='```json\n{"claims": []}\n```'))
    p = panel.aggregate(RUBRIC, passes_with(dict.fromkeys("abcde", 2)), m)
    assert p.verdict == "FAILED" and p.overall == 0.0 and p.dimensions["output"] == 0.0
    assert p.dimensions["workflow"] == 100 and p.confidence == "Low"  # workflow stays visible


def test_high_confidence_and_insufficient_panel(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    p = panel.aggregate(RUBRIC, passes_with({"a": 2, "b": 2, "c": 1, "d": 2, "e": 2}), m)
    assert p.confidence == "High" and p.within_one == 1.0
    bad = [{"pass": 1, "judges": [judge_reply("a", {c: 2 for c in JUDGED}), {"key": "b", "status": "error"}]}]
    q = panel.aggregate(RUBRIC, bad, m)
    assert q.status == "insufficient" and q.overall is None and q.verdict == "not scored"


def test_repeat_passes_report_mean_and_std(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    two = passes_with(dict.fromkeys("abcde", 2)) + [
        {"pass": 2, "judges": [judge_reply(k, {c: 1 for c in JUDGED}) for k in "abcde"]}
    ]
    c = next(x for x in panel.aggregate(RUBRIC, two, m).criteria if x.id == "grounding")
    assert c.median == 1.5 and c.std == 0.5 and c.score == 75.0
    one = next(x for x in panel.aggregate(RUBRIC, two[:1], m).criteria if x.id == "grounding")
    assert one.std is None  # N/A with one pass


def test_corpus_alpha_uses_whole_runs():
    def jd(scores_by_judge):
        return {"passes": [{"judges": [judge_reply(k, s) for k, s in scores_by_judge.items()]}]}

    runs = [
        jd({"a": {"x": 2, "y": 0}, "b": {"x": 2, "y": 0}, "c": {"x": 2, "y": 0}}),
        jd({"a": {"x": 1, "y": 2}, "b": {"x": 1, "y": 2}, "c": {"x": 1, "y": 2}}),
        jd({"a": {"x": 0, "y": 1}, "b": {"x": 0, "y": 2}, "c": {"x": 0, "y": 1}}),
        jd({"a": {"x": 2, "y": 2}, "b": {"x": 0, "y": 0}}),  # a dropped pass (2 valid) doesn't count
    ]
    res = panel.corpus_alpha(runs, samples=200)
    assert res["runs"] == 3 and res["units"] == 6 and res["coders"] == 3
    assert 0.5 < res["alpha"] < 1 and res["ci95"][0] <= res["alpha"] <= res["ci95"][1]


# ---------- AC4 panel runner (fake Bedrock) ----------
CFG = {
    "region": "us-west-2",
    "models": {
        "sonnet": {"id": "us.anthropic.claude-sonnet-5-5", "family": "anthropic"},
        "opus": {"id": "opus", "family": "anthropic"},
        "grok": {"id": "grok", "family": "xai"},
        "kimi": {"id": "kimi", "family": "moonshot"},
        "deepseek": {"id": "deepseek", "family": "deepseek"},
        "mistral": {"id": "mistral", "family": "mistral"},
        "qwen": {"id": "qwen", "family": "alibaba"},
    },
    "prices_per_mtok": {
        k: {"in": 1.0, "out": 2.0} for k in ("opus", "grok", "kimi", "deepseek", "mistral", "qwen")
    },
    "judging": {
        "rubric": str(REPO / "rubrics/geo-dataset-v1.yaml"),
        "panel": ["opus", "grok", "kimi", "deepseek", "mistral"],
        "reserves": ["qwen", "sonnet"],
        "recuse_same_family": True,
        "passes": 1,
    },
}


def good_reply(score=2, refs=("T1", "T9")):
    return json.dumps(
        {
            "criteria": [
                {"id": c, "rationale": "because", "refs": list(refs), "score": score} for c in JUDGED
            ],
            "failure_modes": ["overconfidence", "not_a_mode"],
            "verdict": "fine",
        }
    )


class FakeBedrock:
    """Replies per model ID; a list is consumed one reply per call. Rejects temperature for 'kimi'."""

    def __init__(self, replies):
        self.replies, self.calls, self.lock = replies, [], threading.Lock()

    def converse(self, modelId, system, messages, inferenceConfig):  # noqa: N803 - boto3 names
        with self.lock:
            self.calls.append((modelId, dict(inferenceConfig), len(messages)))
        if modelId == "kimi" and "temperature" in inferenceConfig:
            raise ValueError("temperature is not supported for this model")
        r = self.replies.get(modelId, good_reply())
        if isinstance(r, list):
            r = r.pop(0)
        if isinstance(r, Exception):
            raise r
        return {
            "output": {"message": {"content": [{"text": r}]}},
            "usage": {"inputTokens": 1000, "outputTokens": 100},
        }


def test_same_family_judge_recuses_and_a_reserve_sits():
    seats = judge.seats(CFG, "sonnet")
    assert [s.key for s in seats] == ["qwen", "grok", "kimi", "deepseek", "mistral"]
    assert seats[0].recused_for == "opus"
    assert [s.key for s in judge.seats(CFG, "kimi")] == ["opus", "grok", "qwen", "deepseek", "mistral"]


def test_judge_run_writes_judgement_with_retry_failure_and_ref_filtering(tmp_path):
    run = lgnd_run(tmp_path)
    fake = FakeBedrock(
        {
            "grok": ["not json at all", good_reply(1)],
            "deepseek": RuntimeError("throttled"),
            "mistral": ['{"criteria": []}', '{"criteria": []}'],
        }
    )
    events = []
    jd = judge.judge_run(CFG, run, run.store, client=fake, on_event=events.append)
    saved = json.loads((tmp_path / "runs/run-0001/judgement.json").read_text())
    assert saved["rubric"]["sha256"] == RUBRIC.sha256 and saved["panel"]["status"] == "scored"
    by = {j["key"]: j for j in jd["passes"][0]["judges"]}
    assert by["grok"]["status"] == "ok" and by["grok"]["attempts"] == 2
    assert by["deepseek"]["status"] == "error" and "throttled" in by["deepseek"]["error"]
    assert by["mistral"]["status"] == "error" and by["mistral"]["error"].startswith("parse:")
    assert by["kimi"]["status"] == "ok"  # retried without temperature
    assert by["qwen"]["refs"]["grounding"] == ["T1"] and by["qwen"]["invalid_refs"] == len(JUDGED)
    assert by["qwen"]["failure_modes"] == ["overconfidence"]  # unknown tags dropped
    assert by["qwen"]["cost_usd"] == pytest.approx(1000 / 1e6 + 100 / 1e6 * 2)
    assert saved["panel"]["valid_judges"] == [3] and saved["panel"]["confidence"] == "Low"
    assert [e["type"] for e in events].count("judge") == 5 and events[0]["type"] == "judging"
    assert Run.load(run.store, "run-0001").judgement["run_id"] == "run-0001"


def test_parse_reply_rejects_bad_scores():
    with pytest.raises(judge.JudgeError, match="score must be one of"):
        judge.parse_reply(good_reply(score=3), RUBRIC, {"T1"})
    with pytest.raises(judge.JudgeError, match="missing"):
        judge.parse_reply('{"criteria": [{"id": "grounding", "score": 2}]}', RUBRIC, set())
    fenced = "Sure!\n```json\n" + good_reply() + "\n```"
    assert judge.parse_reply(fenced, RUBRIC, {"T1"})["scores"]["grounding"] == 2


def test_judge_prompt_renders_every_criterion_and_mode():
    text = judge.system_prompt(RUBRIC)
    for c in RUBRIC.judged:
        assert c.id in text and c.anchors[0][:30] in text
    assert "premature_fallback" in text and "<tool_output>" in text and '"criteria": [{' in text


# ---------- AC9 calibration ----------
def test_calibration_verdicts_and_exit_codes():
    base = {c: 2.0 for c in JUDGED}
    rows = calibrate.verdicts(
        RUBRIC,
        base,
        {
            "unscoped": {**base, "tool_arguments": 0.0},
            "fabricated": {**base, "grounding": 1.0, "calibration": 1.0},
            "no_answer": {**base},
        },
    )
    v = {r["perturbation"]: r for r in rows}
    assert v["unscoped"]["verdict"] == "pass" and not v["unscoped"]["non_specific"]
    assert v["fabricated"]["verdict"] == "pass" and v["fabricated"]["non_specific"]
    assert v["no_answer"]["verdict"] == "fail" and calibrate.exit_code(rows) == 1
    zero = calibrate.verdicts(
        RUBRIC, {**base, "tool_arguments": 0.0, "grounding": 0.0, "completeness": 0.0}, {}
    )
    assert {r["verdict"] for r in zero} == {"inconclusive"} and calibrate.exit_code(zero) == 2


def test_calibrate_end_to_end_with_a_discerning_fake_panel(tmp_path):
    run = lgnd_run(tmp_path)

    class Discerning(FakeBedrock):
        def converse(self, modelId, system, messages, inferenceConfig):  # noqa: N803
            text = messages[0]["content"][0]["text"]
            scores = dict.fromkeys(JUDGED, 2)
            if "everywhere (no area given)" in text:
                scores["tool_arguments"] = 0
            if "Northgate Cloud" in text:
                scores["grounding"] = 0
            if "(no final answer)" in text:
                scores["completeness"] = 0
            reply = json.dumps(
                {"criteria": [{"id": c, "rationale": "r", "refs": [], "score": s} for c, s in scores.items()]}
            )
            return {
                "output": {"message": {"content": [{"text": reply}]}},
                "usage": {"inputTokens": 10, "outputTokens": 10},
            }

    out = calibrate.calibrate(CFG, run, run.store, client=Discerning({}))
    assert out["exit_code"] == 0 and {r["verdict"] for r in out["rows"]} == {"pass"}
    assert (tmp_path / "runs/run-0001/calibration.json").is_file()


def test_standard_run_still_judges(tmp_path):
    b = standard_run(tmp_path)
    run = Run.load(FileStore(f"file://{tmp_path}"), b.run_id)
    assert measure.measure(run).area_compliance is None and dossier.build(run).steps


# ---------- Verify-review regressions ----------
def test_within_one_is_per_pass_then_averaged(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    split = [
        {
            "pass": 1,
            "judges": [
                judge_reply(k, {c: v for c in JUDGED}) for k, v in zip("abcde", [0, 2, 2, 2, 2], strict=True)
            ],
        },
        {"pass": 2, "judges": [judge_reply(k, {c: 2 for c in JUDGED}) for k in "abcde"]},
    ]
    p = panel.aggregate(RUBRIC, split, m)
    assert p.within_one == 0.5 and p.confidence == "Medium"  # not 1.0 / High from averaging spreads first


def test_failure_modes_pool_votes_across_passes(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    one = {c: 2 for c in JUDGED}
    passes = [
        {
            "pass": n,
            "judges": [judge_reply(k, one, ["retry_loop"] if (n, k) in tags else []) for k in "abcde"],
        }
        for n in (1, 2)
        for tags in [{(1, "a"), (1, "b"), (1, "c"), (2, "a"), (2, "b"), (2, "c")}]
    ]
    assert [f["id"] for f in panel.aggregate(RUBRIC, passes, m).failure_modes] == ["retry_loop"]  # 6 of 10
    few = [
        {
            "pass": n,
            "judges": [
                judge_reply(k, one, ["retry_loop"] if (n == 1 and k in "abc") else []) for k in "abcde"
            ],
        }
        for n in (1, 2)
    ]
    assert panel.aggregate(RUBRIC, few, m).failure_modes == []  # 3 of 10 pooled votes is no majority


def test_no_valid_judges_reports_no_dimension_scores(tmp_path):
    m = measure.measure(lgnd_run(tmp_path))
    p = panel.aggregate(RUBRIC, [{"pass": 1, "judges": [{"key": k, "status": "error"} for k in "abcde"]}], m)
    assert p.overall is None and p.dimensions == {"workflow": None, "output": None}


CONCAVE = {
    "label": "Ell",
    "source": "test",
    "mode": "enforce",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [[-97, 32], [-96, 32], [-96, 32.2], [-96.8, 32.2], [-96.8, 33], [-97, 33], [-97, 32]]
        ],
    },
}


def test_fabricated_site_is_inside_a_concave_area(tmp_path):
    lon0 = sum(p[0] for p in CONCAVE["geometry"]["coordinates"][0]) / 7
    lat0 = sum(p[1] for p in CONCAVE["geometry"]["coordinates"][0]) / 7
    assert not geometry.contains(CONCAVE["geometry"], lon0, lat0)  # the vertex average is outside the L
    d = dossier.build(lgnd_run(tmp_path, area=CONCAVE))
    fab = dossier.perturb(d, "fabricated")
    lat, lon = (
        float(x) for x in fab.final_answer.split("Northgate Cloud, at ")[1].split(".\n")[0].split(", ")
    )
    assert geometry.contains(CONCAVE["geometry"], lon, lat)


def test_unscoped_rewrites_every_area_description_even_when_trimmed(tmp_path):
    d = dossier.build(lgnd_run(tmp_path))
    step = next(s for s in d.steps if s.kind == "tool")
    step.output = (
        '{"index":"s2","area":"within 60 km of 17.5, 105.2","where":"polygon with 5 vertices","cells":['
        "\n[trimmed 900 chars]"
    )
    out = next(s for s in dossier.perturb(d, "unscoped").steps if s.kind == "tool").output
    assert '"area":"everywhere"' in out and '"where":"everywhere"' in out and "17.5" not in out


def test_calibrate_skips_a_perturbation_that_changes_nothing(tmp_path):
    b = RunBuilder(root=tmp_path, model_key="sonnet", model_id="us.anthropic.claude-sonnet-5-5")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "search_datasets", "input": {}})
    b.tool("search_datasets", {"query": "dc"}, '{"results": []}')  # RODA only: nothing to unscope
    b.model(ANSWER)
    b.run_end()
    b.write(final_output=ANSWER, prices={"sonnet": {"in": 2.0, "out": 10.0}})
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-0001")
    fake = FakeBedrock({})
    out = calibrate.calibrate(CFG, run, run.store, client=fake)
    v = {r["perturbation"]: r for r in out["rows"]}
    assert v["unscoped"]["verdict"] == "skipped" and "changes nothing" in v["unscoped"]["why"]
    assert sum(1 for model, _, _ in fake.calls if model == "qwen") == 3  # base + 2 testable, not 4 panels


def test_infrastructure_failure_is_not_scored_and_replaces_a_stale_judgement(tmp_path):
    """No model call succeeded (expired credentials): the panel isn't asked, and the run stays out of α."""
    b = RunBuilder(root=tmp_path, model_key="kimi", model_id="us.moonshotai.kimi-k3")
    b.run_start()
    b.strands("invoke_agent Strands Agents", status="ERROR")
    b.model("", reasoning=None, in_tok=0, out_tok=0, stop_reason="error")
    expired = "An error occurred (ExpiredTokenException) when calling the ConverseStream operation"
    b.lines[-1]["attributes"]["harness.model.error"] = expired
    b.run_end(status="error")
    b.write(final_output="", status="error")
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-0001")
    assert measure.infrastructure_failure(run) == expired
    (tmp_path / "runs/run-0001/judgement.json").write_text(json.dumps({"run_id": "run-0001", "passes": []}))

    fake, events = FakeBedrock({}), []
    rec = judge.judge_run(CFG, run, run.store, client=fake, on_event=events.append)
    assert fake.calls == [] and rec["judging_cost_usd"] == 0.0
    assert events == [{"type": "not_scored", "cause": expired}]
    again = Run.load(run.store, "run-0001")
    assert again.judgement is None and again.not_scored == {"reason": "infrastructure", "cause": expired}

    from harness.web import view

    assert view.run_row(again)["verdict"] == "not scored"
    assert view.run_view(again)["kpis"]["not_scored_cause"] == expired


def test_a_run_with_one_good_model_call_is_still_judged(tmp_path):
    assert measure.infrastructure_failure(lgnd_run(tmp_path)) is None


TRIBUNAL = {**CFG, "judging": {**CFG["judging"], "panel": ["opus", "deepseek", "kimi"],
                               "reserves": ["mistral", "qwen", "sonnet"]}}  # fmt: skip


def test_tribunal_seats_three_and_a_reserve_stands_in_for_a_failed_judge(tmp_path):
    """harness.yaml's tribunal: three families; Mistral sits for the recused judge; a failure is covered."""
    assert [s.key for s in judge.seats(TRIBUNAL, "sonnet")] == ["mistral", "deepseek", "kimi"]
    assert [s.key for s in judge.seats(TRIBUNAL, "kimi")] == ["opus", "deepseek", "mistral"]
    seated = judge.seats(TRIBUNAL, "kimi")
    # sonnet shares opus's family, so qwen is the only spare
    assert [s.key for s in judge.spare_seats(TRIBUNAL, "kimi", seated)] == ["qwen"]

    run = lgnd_run(tmp_path)  # a Sonnet run: mistral sits for opus; qwen is the only spare
    fake, events = FakeBedrock({"kimi": RuntimeError("throttled")}), []
    jd = judge.judge_run(TRIBUNAL, run, run.store, client=fake, on_event=events.append)
    judges = jd["passes"][0]["judges"]
    assert [(j["key"], j["status"], j.get("stood_in_for")) for j in judges] == [
        ("mistral", "ok", None), ("deepseek", "ok", None), ("kimi", "error", None), ("qwen", "ok", "kimi"),
    ]  # fmt: skip
    assert jd["panel"]["valid_judges"] == [3] and jd["panel"]["status"] == "scored"
    assert jd["panel"]["confidence"] == "High"  # the stand-in restored a full tribunal
    assert [e.get("key") for e in events if e["type"] == "judge"][-1] == "qwen"


def test_a_tribunal_short_a_vote_is_not_scored_by_two(tmp_path):
    run = lgnd_run(tmp_path, model_key="kimi")  # seats opus, deepseek, mistral; spares: qwen only
    fake = FakeBedrock({"deepseek": RuntimeError("down"), "qwen": RuntimeError("down")})
    jd = judge.judge_run(TRIBUNAL, run, run.store, client=fake)
    assert jd["panel"]["valid_judges"] == [2] and jd["panel"]["status"] != "scored"
