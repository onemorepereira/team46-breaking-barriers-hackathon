"""The real agent code path with only the model and tool faked (HARNESS_TEST_SCRIPT), via `harness run`."""

import json
import os
import subprocess
import sys
from pathlib import Path

from analysis.check import check_run
from analysis.provenance import MATCHED, grade
from analysis.store import FileStore
from analysis.trace import Run

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tests/fixtures/scripted_run.json"


def config(tmp_path):
    cfg = {
        "archive_uri": f"file://{tmp_path}/archive",
        "local_archive_uri": f"file://{tmp_path}/archive",
        "out_dir": str(tmp_path / "out"),
        "backend": "local",
        "local_exporter": "console",
        "models": {"scripted": {"id": "scripted", "max_tokens": 1000, "request_fields": {}}},
        "prices_per_mtok": {"scripted": {"in": 1.0, "out": 5.0}},
    }
    (tmp_path / "harness.yaml").write_text(json.dumps(cfg))
    return tmp_path / "harness.yaml"


def run_harness(tmp_path, *args, script=SCRIPT):
    env = {
        **os.environ,
        "HARNESS_TEST_SCRIPT": str(script),
        "HARNESS_CONSOLE_PATH": str(tmp_path / "console.jsonl"),
    }
    return subprocess.run(
        [sys.executable, "-m", "harness.cli", "--config", str(config(tmp_path)), *args],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )  # fmt: skip


def only_run(tmp_path):
    runs = list((tmp_path / "archive/runs").iterdir())
    assert len(runs) == 1
    return Run.load(FileStore(f"file://{tmp_path}/archive"), runs[0].name)


def test_scripted_run_end_to_end(tmp_path):
    r = run_harness(tmp_path, "run", "--prompt", "prompts/dallas-dc.md", "--model", "scripted")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claims 2 matched / 0 mismatch / 0 unsourced" in r.stdout
    run = only_run(tmp_path)
    assert run.status == "ok" and run.manifest["status"] == "ok" and run.manifest["ended_at"]
    assert check_run(run) == []
    assert [c.status for c in grade(run).claims] == [MATCHED, MATCHED]
    # the model saw the ref label; the archived raw result doesn't contain it
    delta = json.dumps(run.model_results[1].json_attr("harness.model.input_messages_delta"))
    assert "[ref T1]" in delta and "[ref" not in run.tool_result_text(run.tool_results[0])
    assert run.model_results[0].attr("harness.reasoning.text") == "Look up the facility first."
    # 100% of decision spans archived (spike S2's check)
    harness_spans = [s for s in run.spans if s.scope == "harness"]
    assert run.run_end.attr("harness.decision_spans_emitted") == len(harness_spans)
    kinds = {s.span_kind for s in run.spans}
    assert {"agent", "cycle", "model", "tool", "harness"} <= kinds
    # index points to the run's archive, so check/replay find it
    chk = run_harness(tmp_path, "check", run.run_id)
    assert chk.returncode == 0 and "0 missing fields" in chk.stdout


def test_step_limit_ends_run_as_limit_exceeded(tmp_path):
    loop = tmp_path / "loop.json"
    loop.write_text(json.dumps([{"tool": "lookup_facility", "input": {"name": "DA11"}}]))  # repeats forever
    r = run_harness(tmp_path, "run", "--prompt", "prompts/dallas-dc.md", "--model", "scripted", script=loop)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "status limit_exceeded: step limit 40 reached" in r.stdout
    run = only_run(tmp_path)
    assert run.run_end.attr("harness.status") == "limit_exceeded"
    assert len(run.model_results) + len(run.tool_results) == 40
    assert any(t.attr("harness.tool.repeat_of") == "T1" for t in run.tool_results)
    assert check_run(run) == []


def test_refuses_without_prices(tmp_path):
    cfg = config(tmp_path)
    data = json.loads(cfg.read_text())
    data["prices_per_mtok"] = {}
    cfg.write_text(json.dumps(data))
    env = {**os.environ, "HARNESS_TEST_SCRIPT": str(SCRIPT)}
    r = subprocess.run(
        [sys.executable, "-m", "harness.cli", "--config", str(cfg), "run", "--prompt", "prompts/dallas-dc.md",
         "--model", "scripted"], cwd=REPO, env=env, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert r.returncode == 2 and "prices_per_mtok.scripted is not set" in r.stdout
    assert not (tmp_path / "archive").exists()


def suite_file(tmp_path, prompts, models):
    p = tmp_path / "suite.yaml"
    p.write_text(json.dumps({"suite": "t-suite", "prompts": prompts, "models": models, "backend": "local"}))
    return p


def test_suite_runs_prompt_major_and_compares(tmp_path):
    cfg = config(tmp_path)
    data = json.loads(cfg.read_text())
    data["models"]["scripted2"] = {"id": "scripted", "max_tokens": 1000, "request_fields": {}}
    data["prices_per_mtok"]["scripted2"] = {"in": 1.0, "out": 5.0}
    cfg.write_text(json.dumps(data))
    suite = suite_file(
        tmp_path, ["prompts/dallas-dc.md", "prompts/dallas-dc-strict.md"], ["scripted", "scripted2"]
    )
    env = {**os.environ, "HARNESS_TEST_SCRIPT": str(SCRIPT)}
    cmd = [sys.executable, "-m", "harness.cli", "--config", str(cfg), "run", "--suite", str(suite)]
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    suite_id = r.stdout.splitlines()[0].split()[1].rstrip(":")
    assert "done: 4/4 runs → harness compare" in r.stdout
    manifest = json.loads((tmp_path / f"archive/suites/{suite_id}/suite.json").read_text())
    assert len(manifest["run_ids"]) == 4
    runs = [
        json.loads((tmp_path / f"archive/runs/{rid}/run.json").read_text()) for rid in manifest["run_ids"]
    ]
    assert [(x["prompt_file"], x["model_key"]) for x in runs] == [
        ("prompts/dallas-dc.md", "scripted"), ("prompts/dallas-dc.md", "scripted2"),
        ("prompts/dallas-dc-strict.md", "scripted"), ("prompts/dallas-dc-strict.md", "scripted2"),
    ]  # fmt: skip
    c = subprocess.run([sys.executable, "-m", "harness.cli", "--config", str(cfg), "compare", suite_id],
                       cwd=REPO, capture_output=True, text=True, timeout=60)  # fmt: skip
    assert c.returncode == 0 and "(4 rows)" in c.stdout


def test_suite_refusals(tmp_path):
    cfg = config(tmp_path)
    data = json.loads(cfg.read_text())
    data["max_runs_per_suite"] = 1
    cfg.write_text(json.dumps(data))
    env = {**os.environ, "HARNESS_TEST_SCRIPT": str(SCRIPT)}

    def run(suite):
        cmd = [sys.executable, "-m", "harness.cli", "--config", str(cfg), "run", "--suite", str(suite)]
        return subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=60)

    too_many = run(
        suite_file(tmp_path, ["prompts/dallas-dc.md", "prompts/dallas-dc-strict.md"], ["scripted"])
    )
    assert too_many.returncode == 2 and "suite has 2 runs; max_runs_per_suite is 1" in too_many.stdout
    bad_model = run(suite_file(tmp_path, ["prompts/dallas-dc.md"], ["opus"]))
    assert "unknown model key 'opus' (known: scripted)" in bad_model.stdout
    data["max_runs_per_suite"], data["max_suite_usd"] = 8, 0.5
    cfg.write_text(json.dumps(data))
    costly = run(suite_file(tmp_path, ["prompts/dallas-dc.md"], ["scripted"]))
    assert "exceeds max_suite_usd $0" in costly.stdout and costly.returncode == 2
    assert not (tmp_path / "archive/runs").exists()
