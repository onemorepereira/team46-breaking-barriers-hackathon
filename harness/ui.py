"""`harness ui`: a lightweight local page to start a run, watch it live, and see the NAIP tiles it found.

The agent runs locally with the console exporter writing one JSON span per line to out/<run>/live.jsonl.
The server tails that file and streams the harness.* decision spans to the page as server-sent events.
Standard library only; bound to 127.0.0.1.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from analysis import report
from analysis.store import open_store
from analysis.trace import Run
from harness import config as config_mod
from harness import invoke
from harness.manifest import Index

PAGE = Path(__file__).with_name("ui.html")


class RunState:
    def __init__(self, run_id: str, live: Path) -> None:
        self.run_id = run_id
        self.live = live
        self.done = False
        self.final: dict[str, Any] | None = None


RUNS: dict[str, RunState] = {}


def _rows(table: Any) -> list[dict[str, Any]]:
    """LGND returns {"columns": [...], "rows": [[...], ...]}; turn it into dicts."""
    if not isinstance(table, dict) or not isinstance(table.get("rows"), list):
        return []
    cols = table.get("columns") or []
    return [dict(zip(cols, r, strict=False)) for r in table["rows"] if isinstance(r, list)]


def lgnd_extras(name: str, result: str) -> dict[str, Any]:
    """Chips (with bbox) from search results, and per-chip verdicts from imagery checks."""
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    chips = [
        {k: r.get(k) for k in ("node", "chip_id", "lat", "lon", "bbox", "observed", "similarity")}
        for r in _rows(data.get("matches"))
        if isinstance(r.get("bbox"), list) and len(r["bbox"]) == 4
    ]
    verdicts = [
        {"node": r.get("node"), "answer": r.get("answer"), "reason": r.get("reason")}
        for r in _rows(data.get("places"))
        if r.get("node")
    ]
    out: dict[str, Any] = {}
    if chips:
        out["chips"] = chips
    if verdicts:
        out["verdicts"] = verdicts
        out["verdict"] = data.get("verdict")
    return out


def span_event(span: dict[str, Any]) -> dict[str, Any] | None:
    """One console-exported span line -> one UI event (harness.* decision spans only)."""
    name, a = span.get("name", ""), span.get("attributes", {}) or {}
    if name == "harness.run.start":
        tools = json.loads(a.get("harness.tools.available", "[]") or "[]")
        servers: dict[str, int] = {}
        for t in tools:
            servers[t.get("server", "?")] = servers.get(t.get("server", "?"), 0) + 1
        return {"type": "start", "servers": servers}
    if name == "harness.model_result":
        out = json.loads(a.get("harness.model.output", "{}") or "{}")
        content = out.get("content", []) if isinstance(out, dict) else []
        uses = [c["toolUse"] for c in content if isinstance(c, dict) and "toolUse" in c]
        text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
        return {
            "type": "model",
            "call": a.get("harness.model.call_index"),
            "reasoning": (a.get("harness.reasoning.text") or "")[:1500],
            "text": text[:1500],
            "tool_uses": [{"name": u.get("name"), "input": u.get("input")} for u in uses],
            "stop": a.get("harness.stop_reason"),
            "in": a.get("harness.usage.input_tokens"),
            "out": a.get("harness.usage.output_tokens"),
            "ms": a.get("harness.model.latency_ms"),
        }
    if name == "harness.tool_result":
        result = a.get("harness.tool.result", "") or ""
        ev = {
            "type": "tool",
            "ref": a.get("harness.tool.ref"),
            "server": a.get("harness.tool.server"),
            "name": a.get("harness.tool.name"),
            "args": a.get("harness.tool.arguments"),
            "status": a.get("harness.tool.status"),
            "ms": a.get("harness.tool.latency_ms"),
            "attempt": a.get("harness.tool.attempt"),
            "head": result[:600],
        }
        if a.get("harness.tool.server") == "lgnd":
            ev.update(lgnd_extras(str(a.get("harness.tool.name")), result))
        return ev
    if name == "harness.run.end":
        return {"type": "end", "status": a.get("harness.status")}
    return None


def start_run(cfg: config_mod.Config, index: Index, prompt: str, model: str) -> str:
    out = Path(cfg["out_dir"]) / "ui"
    out.mkdir(parents=True, exist_ok=True)
    prompt_file = out / f"prompt-{uuid.uuid4().hex[:8]}.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    plan = invoke.plan_run(cfg, prompt_file=str(prompt_file), model_key=model, backend="local")
    live = Path(cfg["out_dir"]) / plan.run_id / "live.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.touch()
    state = RunState(plan.run_id, live)
    RUNS[plan.run_id] = state

    def work() -> None:
        from harness.cli import write_report

        env = {"HARNESS_EXPORTER": "console", "HARNESS_CONSOLE_PATH": str(live.resolve())}
        try:
            outcome = invoke.execute(cfg, index, plan, extra_env=env)
            run = Run.load(open_store(plan.archive_uri), plan.run_id)
            write_report(cfg, run)
            rep = report.analyze(run)
            state.final = {
                "type": "done",
                "status": outcome.status,
                "error": outcome.error,
                "claims": [
                    {"claim": c.claim, "value": c.value, "ref": c.ref, "status": c.status}
                    for c in rep.prov.claims
                ],
                "block_missing": rep.prov.claims_block_missing,
                "signals": rep.sig.as_dict(),
                "missing_fields": len(rep.missing),
                "report": f"/report/{plan.run_id}",
                "final_output": run.final_output[:4000],
            }
        except Exception as e:  # noqa: BLE001 - shown on the page
            state.final = {
                "type": "done",
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "claims": [],
            }
        finally:
            state.done = True

    threading.Thread(target=work, name=f"ui-run-{plan.run_id}", daemon=True).start()
    return plan.run_id


def make_handler(cfg: config_mod.Config, index: Index) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return None

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: Any) -> None:
            self._send(code, json.dumps(data).encode(), "application/json")

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/models":
                self._json(200, {"models": list(cfg["models"] or {})})
            elif path.startswith("/api/events/"):
                self._events(path.rsplit("/", 1)[-1])
            elif path.startswith("/report/"):
                run_id = path.rsplit("/", 1)[-1]
                rp = Path(cfg["out_dir"]) / run_id / "report.html"
                if "/" in run_id or ".." in run_id or not rp.is_file():
                    self._send(404, b"no report", "text/plain")
                else:
                    self._send(200, rp.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/run":
                self._send(404, b"not found", "text/plain")
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("content-length", "0") or 0)) or b"{}")
                prompt, model = str(body.get("prompt", "")).strip(), str(body.get("model", ""))
                if not prompt:
                    self._json(400, {"error": "Type a prompt first."})
                    return
                self._json(200, {"run_id": start_run(cfg, index, prompt, model)})
            except invoke.RunRefused as e:
                self._json(400, {"error": str(e)})

        def _events(self, run_id: str) -> None:
            state = RUNS.get(run_id)
            if state is None:
                self._send(404, b"unknown run", "text/plain")
                return
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("cache-control", "no-cache")
            self.end_headers()
            pos = 0
            try:
                while True:
                    with state.live.open("r", encoding="utf-8") as f:
                        f.seek(pos)
                        chunk = f.read()
                        pos = f.tell()
                    for line in chunk.splitlines():
                        try:
                            ev = span_event(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                        if ev:
                            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                    self.wfile.flush()
                    if state.done and not chunk:
                        self.wfile.write(f"data: {json.dumps(state.final)}\n\n".encode())
                        self.wfile.flush()
                        return
                    time.sleep(0.4)
            except (BrokenPipeError, ConnectionResetError):
                return

    return Handler


def serve(cfg: config_mod.Config, port: int) -> int:
    index = Index(cfg["out_dir"])
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg, index))
    print(f"harness ui on http://127.0.0.1:{port}  (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
