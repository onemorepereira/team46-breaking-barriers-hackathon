"""AC4: the same agent activity reaches two different exporters with only config changed (design ADR-2).

Each case runs in its own subprocess, so each gets a fresh, explicitly passed tracer provider.
"""

import collections
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tests/fixtures/scripted_run.json"
AGENT_SCOPES = {"strands.telemetry.tracer", "harness"}


class Receiver(BaseHTTPRequestHandler):
    spans: list[tuple[str, str]] = []

    def do_POST(self):  # noqa: N802 - http.server API
        body = self.rfile.read(int(self.headers["Content-Length"]))
        req = ExportTraceServiceRequest()
        req.ParseFromString(body)
        for rs in req.resource_spans:
            for ss in rs.scope_spans:
                for sp in ss.spans:
                    attrs = {a.key: a.value.string_value for a in sp.attributes}
                    Receiver.spans.append((ss.scope.name, attrs.get("harness.span_kind", "")))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def payload(tmp_path, run_id):
    p = tmp_path / f"{run_id}.json"
    p.write_text(json.dumps({
        "schema_version": 1, "run_id": run_id, "suite_id": None, "prompt": "Find DA11.",
        "prompt_file": "prompts/tasks/dallas-dc.md", "prompt_sha256": "0" * 64, "model_id": "scripted",
        "model_params": {"max_tokens": 1000, "request_fields": {}},
        "limits": {"max_steps": 40, "max_input_tokens": 400000, "wall_clock_s": 60, "tool_timeout_s": 60},
    }))  # fmt: skip
    return p


def run_agent(tmp_path, run_id, **env):
    e = {
        **os.environ,
        "HARNESS_TEST_SCRIPT": str(SCRIPT),
        "HARNESS_ARCHIVE_URI": f"file://{tmp_path}/a",
        **env,
    }
    r = subprocess.run([sys.executable, "-m", "agent.local", str(payload(tmp_path, run_id))], cwd=REPO, env=e,
                       capture_output=True, text=True, timeout=120)  # fmt: skip
    assert r.returncode == 0, r.stderr


def kinds(pairs):
    return collections.Counter(k for scope, k in pairs if scope in AGENT_SCOPES)


def test_same_agent_spans_through_otlp_and_console(tmp_path):
    Receiver.spans = []
    server = HTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
        run_agent(tmp_path, "otlp", HARNESS_EXPORTER="otlp", OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=endpoint)
        console = tmp_path / "console.jsonl"
        run_agent(tmp_path, "console", HARNESS_EXPORTER="console", HARNESS_CONSOLE_PATH=str(console))
    finally:
        server.shutdown()
    otlp_kinds = kinds(Receiver.spans)
    console_spans = [json.loads(line) for line in console.read_text().splitlines() if line.strip()]
    # ConsoleSpanExporter's JSON omits the scope, so use our archive (which records it) to pick agent spans
    archived = [
        json.loads(x) for x in (tmp_path / "a/runs/console/spans-0001.jsonl").read_text().splitlines()
    ]
    agent_ids = {f"0x{s['span_id']}" for s in archived if s["scope"] in AGENT_SCOPES}
    console_kinds = collections.Counter(
        s["attributes"]["harness.span_kind"] for s in console_spans if s["context"]["span_id"] in agent_ids
    )
    assert otlp_kinds == console_kinds
    assert otlp_kinds["model"] == 2 and otlp_kinds["tool"] == 1 and otlp_kinds["harness"] == 5
