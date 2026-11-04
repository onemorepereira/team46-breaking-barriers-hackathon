import json

import pytest

from analysis.check import check_run, full_input
from analysis.trace import Run
from core.store import FileStore
from tests.fixtures.builder import DA11_RESULT, RunBuilder, standard_run


def load(tmp_path, run_id="run-0001"):
    return Run.load(FileStore(f"file://{tmp_path}"), run_id)


def fields(missing):
    return [m.field for m in missing]


def test_complete_run_has_no_missing_fields(tmp_path):
    standard_run(tmp_path)
    assert check_run(load(tmp_path)) == []


def test_full_input_reassembles_from_deltas(tmp_path):
    standard_run(tmp_path)
    run = load(tmp_path)
    msgs = full_input(run, 1)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]


def _two_call_run(tmp_path, *, model_kw=None, tool_kw=None):
    b = RunBuilder(root=tmp_path)
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "x", "input": {}}, **(model_kw or {}))
    b.tool("get_dataset_details", {"slug": "s"}, DA11_RESULT, **(tool_kw or {}))
    b.model("done")
    b.run_end()
    b.write(final_output="done")
    return load(tmp_path)


@pytest.mark.parametrize(
    "drop",
    ["harness.system_prompt.sha256", "harness.model.input_messages_delta", "harness.usage.input_tokens"],
)
def test_model_result_missing_field_is_reported(tmp_path, drop):
    run = _two_call_run(tmp_path, model_kw={"drop": (drop,)})
    assert drop in fields(check_run(run))


def test_reasoning_needs_text_or_explicit_false(tmp_path):
    run = _two_call_run(tmp_path, model_kw={"drop": ("harness.reasoning.text",)})
    assert fields(check_run(run)) == ["harness.reasoning.text"]
    tmp2 = tmp_path / "b"
    run2 = _two_call_run(tmp2, model_kw={"reasoning": None})  # available=false is a normal value
    assert check_run(run2) == []


@pytest.mark.parametrize(
    "drop", ["harness.tool.arguments", "harness.tool.latency_ms", "harness.tool.attempt"]
)
def test_tool_result_missing_field_is_reported(tmp_path, drop):
    run = _two_call_run(tmp_path, tool_kw={"drop": (drop,)})
    assert fields(check_run(run)) == [drop]


def test_missing_result_file(tmp_path):
    run = _two_call_run(tmp_path, tool_kw={"write_file": False})
    assert fields(check_run(run)) == ["tool result file missing from archive"]


def test_hash_mismatch(tmp_path):
    run = _two_call_run(tmp_path, tool_kw={"corrupt_hash": True})
    assert fields(check_run(run)) == ["tool result file hash mismatch"]


def test_trimmed_history(tmp_path):
    run = _two_call_run(tmp_path, model_kw={"trim": True})
    assert any("trimmed" in f for f in fields(check_run(run)))


def test_call_index_gap(tmp_path):
    b = RunBuilder(root=tmp_path)
    b.run_start()
    b.model("a", call_index=0)
    b.model("b", call_index=2)
    b.run_end()
    b.write(final_output="b")
    assert any("call_index gap" in f for f in fields(check_run(load(tmp_path))))


def test_delta_length_mismatch(tmp_path):
    run = _two_call_run(tmp_path, model_kw={"delta_override": []})
    assert any("input_messages_delta length" in f for f in fields(check_run(run)))


def test_missing_run_start(tmp_path):
    b = RunBuilder(root=tmp_path)
    b.model("x")
    b.write(final_output="x")
    assert "span missing" in fields(check_run(load(tmp_path)))


def test_spans_after_run_end_and_non_agent_scopes_are_ignored(tmp_path):
    b = standard_run(tmp_path)
    b.span("MCP send tools/call x", scope="mcp")
    b.span("harness.model_result", {"harness.after_end": True})  # incomplete, but after end
    b.write(final_output="x")
    run = load(tmp_path)
    assert all(s.scope != "mcp" for s in run.spans)
    assert check_run(run) == []
    assert json.loads((tmp_path / "runs/run-0001/run.json").read_text())["run_id"] == "run-0001"


def test_archive_errors_and_lost_decision_spans_fail_the_check(tmp_path):
    b = standard_run(tmp_path)
    end = b.lines[-1]
    end["attributes"]["harness.decision_spans_emitted"] = 99  # more emitted than archived: a lost part
    b.write(final_output="x")
    assert any("decision spans emitted, " in f for f in fields(check_run(load(tmp_path))))
    import json as _json

    rj = tmp_path / "runs/run-0001/result.json"
    data = _json.loads(rj.read_text())
    data["archive_errors"] = 2
    rj.write_text(_json.dumps(data))
    assert "2 archive write(s) failed" in fields(check_run(load(tmp_path)))
