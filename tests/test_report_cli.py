"""AC7, AC8, AC9, AC11 through the real `harness` entry point."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from analysis import report
from analysis.provenance import grade
from analysis.summary import build, filter_narrative
from analysis.trace import Run
from core.store import FileStore
from harness.cli import main
from tests.fixtures.builder import DA11_RESULT, RunBuilder, standard_run

REPO = Path(__file__).resolve().parents[1]


def write_config(tmp_path, **extra):
    cfg = {"archive_uri": f"file://{tmp_path}/archive", "out_dir": str(tmp_path / "out"), **extra}
    p = tmp_path / "harness.yaml"
    p.write_text(json.dumps(cfg))  # JSON is valid YAML
    return p


def harness(tmp_path, *args, env=None):
    e = {**os.environ, "HARNESS_GENERATED_AT": "2026-11-04T00:00:00Z", **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "harness.cli", "--config", str(tmp_path / "harness.yaml"), *args],
        cwd=REPO, env=e, capture_output=True, text=True, timeout=60,
    )  # fmt: skip


def troubled_run(root):
    b = RunBuilder(root=root, run_id="run-trouble")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "q", "input": {}})
    b.tool(
        "search_datasets", {"query": "dc"}, "error: timeout", status="error", ref="T1", span_status="ERROR"
    )
    b.tool("search_datasets", {"query": "dc"}, DA11_RESULT, attempt=1, ref="T1")
    b.tool("get_dataset_details", {"slug": "osm"}, DA11_RESULT, ref="T2", repeat_of="T1")
    out = '```json\n{"claims": [{"claim": "op", "value": "Equinix", "ref": "T1"}, {"claim": "bad", "value": "Nope", "ref": "T2"}, {"claim": "free", "value": "x"}]}\n```'  # noqa: E501
    b.model(out, stop_reason="max_tokens")
    b.run_end("limit_exceeded")
    b.write(final_output=out, status="limit_exceeded")
    return b


def test_trouble_spots_are_all_named_with_real_span_ids(tmp_path):
    troubled_run(tmp_path)
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-trouble")
    summ = build(run, grade(run))
    reasons = " | ".join(t.reason for t in summ.trouble_spots)
    # (Strands' execute_tool ERROR span is not a separate trouble spot: the tool_result already names it)
    for needle in ["returned an error", "retried", "repeats T1", "max_tokens", "is mismatch",
                   "is unsourced", "limit exceeded"]:  # fmt: skip
        assert needle in reasons, needle
    ids = run.span_ids()
    assert all(t.span_id in ids for t in summ.trouble_spots)
    assert all(s.span_id in ids for s in summ.steps)
    # one failed tool call is one error and one "returned an error" trouble spot, not two (Verify gate)
    from analysis.signals import compute

    assert compute(run).errors == 1
    assert sum("T1" in t.reason and "error" in t.reason for t in summ.trouble_spots) == 1
    assert [s.label for s in summ.steps if s.kind == "tool"] == ["T1 search_datasets", "T1 search_datasets",
                                                                  "T2 get_dataset_details"]  # fmt: skip


def test_narrative_filter_drops_invented_span_ids():
    text, dropped = filter_narrative("see 0000000000000001 and deadbeefdeadbeef", {"0000000000000001"})
    assert dropped == ["deadbeefdeadbeef"] and "0000000000000001" in text and "deadbeef" not in text


def test_report_has_every_section_and_escapes(tmp_path):
    b = RunBuilder(root=tmp_path / "archive")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "q", "input": {}})
    b.tool("get_dataset_details", {"slug": "osm-dc"}, "<script>alert(1)</script> Equinix")
    out = '<script>alert(2)</script>\n```json\n{"claims": [{"claim": "<script>x</script>", "value": "Equinix", "ref": "T1"}]}\n```'  # noqa: E501
    b.model(out)
    b.run_end()
    b.write(final_output=out)
    write_config(tmp_path)
    r = harness(tmp_path, "replay", "run-0001")
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "out/run-0001/report.html").read_text()
    for section in ["Tools available", "Datasets accessed", "Summary", "Trouble spots", "Timeline",
                    "Workflow signals", "Claim provenance", "Panel score", "Not judged",
                    "estimated cost usd", "runtime s", "osm-dc", "get_dataset_details"]:  # fmt: skip
        assert section in html, section
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_final_answer_renders_markdown_and_tucks_the_claims_json_away(tmp_path):
    out = (
        "## Findings\n\n**Confirmed:**\n\n| Site | Coordinates |\n|---|---|\n| Napa | 38.38, -122.36 |\n\n"
        "[bad](javascript:alert(1)) <img src=x onerror=alert(1)>\n\n"
        '```json\n{"claims": [{"claim": "Napa", "value": "38.38, -122.36", "ref": "T1"}]}\n```'
    )
    b = RunBuilder(root=tmp_path)
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "q", "input": {}})
    b.tool("get_dataset_details", {"slug": "osm-dc"}, "Napa 38.38, -122.36")
    b.model(out)
    b.run_end()
    b.write(final_output=out)
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-0001")
    html = report.render_run(report.analyze(run), "2026-11-04T00:00:00Z")
    answer = html[html.index("<h2>Final answer</h2>") :]
    assert "<h2>Findings</h2>" in answer and "<strong>Confirmed:</strong>" in answer
    assert "<td>Napa</td>" in answer and "**" not in answer and "|---|" not in answer
    assert "<img" not in answer and "&lt;img" in answer and 'href="javascript:' not in answer
    assert "<details>" in answer and '"claim": "Napa"' in answer.replace("&#34;", '"')


@pytest.mark.disable_socket
def test_replay_is_deterministic_and_offline_and_ignores_current_prices(tmp_path, monkeypatch):
    standard_run(tmp_path / "archive")
    cfg = write_config(tmp_path, prices_per_mtok={"haiku": {"in": 999, "out": 999}})
    monkeypatch.setenv("HARNESS_GENERATED_AT", "2026-11-04T00:00:00Z")
    run = Run.load(FileStore(f"file://{tmp_path}/archive"), "run-0001")
    direct = report.render_run(report.analyze(run), "2026-11-04T00:00:00Z")
    assert main(["--config", str(cfg), "replay", "run-0001"]) == 0
    replayed = (tmp_path / "out/run-0001/report.html").read_text()
    assert replayed == direct
    # cost from the run.json snapshot: 3000 in x $1 + 400 out x $5 per Mtok = $0.005, not the 999 config
    assert "<b>0.005</b>" in replayed and "3.3966" not in replayed


def test_check_command_exit_codes(tmp_path):
    standard_run(tmp_path / "archive")
    write_config(tmp_path)
    ok = harness(tmp_path, "check", "run-0001")
    assert ok.returncode == 0 and "0 missing fields" in ok.stdout
    (tmp_path / "archive/runs/run-0001/tool_results/T1.a0.txt").unlink()
    bad = harness(tmp_path, "check", "run-0001")
    assert bad.returncode == 1 and re.search(
        r"span \w+ \(harness.tool_result\): tool result file missing", bad.stdout
    )
    missing = harness(tmp_path, "replay", "nope")
    assert missing.returncode == 1 and "no archive for run nope" in missing.stderr


def test_compare_four_runs_from_manifest(tmp_path):
    arch = tmp_path / "archive"
    ids = []
    for i, model in enumerate(["haiku", "sonnet", "haiku", "sonnet"]):
        rid = f"run-{i}"
        standard_run(arch, run_id=rid, suite_id="dallas-dc-v1-20261104T1012", model_key=model)
        ids.append(rid)
    (arch / "suites/dallas-dc-v1-20261104T1012").mkdir(parents=True)
    (arch / "suites/dallas-dc-v1-20261104T1012/suite.json").write_text(json.dumps({"run_ids": ids}))
    write_config(tmp_path)
    r = harness(tmp_path, "compare", "dallas-dc-v1-20261104T1012")
    assert r.returncode == 0 and "(4 rows)" in r.stdout
    csv_text = (tmp_path / "out/dallas-dc-v1-20261104T1012/compare.csv").read_text().splitlines()
    assert len(csv_text) == 5 and csv_text[0].startswith("run_id,prompt_file,model_key")
    assert all(",3,0,0," in line for line in csv_text[1:])  # matched,mismatch,unsourced
    assert harness(tmp_path, "compare", "nope").stdout.startswith("no suite manifest")


def test_analysis_is_fast_for_1000_spans(tmp_path):
    b = RunBuilder(root=tmp_path)
    b.run_start()
    for i in range(330):
        b.model("", tool_use={"toolUseId": f"tooluse_T{i + 1}", "name": "q", "input": {}}, reasoning=None)
        b.tool("search_datasets", {"query": str(i)}, DA11_RESULT)
    b.model("done")
    b.run_end()
    b.write(final_output="done")
    t0 = time.perf_counter()
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-0001")
    assert len(run.all_spans) >= 1000
    report.render_run(report.analyze(run), "now")
    assert time.perf_counter() - t0 < 5
