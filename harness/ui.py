"""`harness ui`: a lightweight local page to start a run, watch it live, and see the NAIP tiles it found.

The agent runs locally with the console exporter writing one JSON span per line to out/<run>/live.jsonl.
The server tails that file and streams the harness.* decision spans to the page as server-sent events.
Standard library only; bound to 127.0.0.1.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from analysis import report
from analysis.trace import Run
from core import geometry
from core.store import open_store
from harness import area as geo
from harness import config as config_mod
from harness import imagery, invoke
from harness.manifest import Index
from tools.lgnd import descriptors as lgnd
from tools.lgnd import results as lgnd_results

PAGE = Path(__file__).with_name("ui.html")


class RunState:
    def __init__(self, run_id: str, live: Path) -> None:
        self.run_id = run_id
        self.live = live
        self.done = False
        self.final: dict[str, Any] | None = None
        self.area: geo.Area | None = None  # the search area read from the prompt, when it has one
        self.area_event: dict[str, Any] | None = None  # sent first on the stream once resolved
        self.chip_checks: dict[str, bool] = {}

    def annotate(self, ev: dict[str, Any]) -> None:
        """Add each chip's display tile, and mark it inside/outside the prompt's area (ground truth)."""
        for c in ev.get("chips", []):
            c["tile_url"] = imagery.tile_url(c.get("index"), c["bbox"])
            c["tile_source"] = imagery.ATTRIBUTION.get(c.get("index") or "", imagery.ATTRIBUTION["s2"])
        geom = self.area.geometry if self.area else None
        if not geom:
            return
        for c in ev.get("chips", []):
            try:
                c["in_area"] = geometry.contains(geom, float(c["lon"]), float(c["lat"]))
            except (TypeError, ValueError, KeyError):
                continue
            self.chip_checks[str(c["node"])] = bool(c["in_area"])


RUNS: dict[str, RunState] = {}


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
        if a.get("harness.tool.server") == lgnd.SERVER:
            ev.update(lgnd_results.extras(result))
            try:
                area = (json.loads(a.get("harness.tool.arguments") or "{}").get("scope") or {}).get("area")
            except (json.JSONDecodeError, AttributeError):
                area = None
            if isinstance(area, dict) and {"lat", "lon"} <= area.keys():
                ev["area"] = area
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
        if not os.environ.get("HARNESS_TEST_SCRIPT"):
            state.area, state.area_event = geo.area_for_prompt(cfg, prompt)
            mode = str(cfg.get("area_mode") or "enforce")
            invoke.attach_area(plan, geo.payload_area(state.area, mode))
            if state.area_event is not None:
                state.area_event["mode"] = mode
        else:
            state.area_event = {"type": "area", "label": None, "note": "Scripted test run: no area check."}
        try:
            outcome = invoke.execute(cfg, index, plan, extra_env=env)
            run = Run.load(open_store(plan.archive_uri), plan.run_id)
            write_report(cfg, run)
            rep = report.analyze(run)
            claims: list[dict[str, Any]] = [
                {"claim": c.claim, "value": c.value, "ref": c.ref, "status": c.status}
                for c in rep.prov.claims
            ]
            area_check = None
            if state.area and state.area.geometry:
                geom = state.area.geometry
                for c in claims:
                    pair = geometry.coordinate_pair(c["value"])
                    if pair:
                        c["in_area"] = geometry.contains(geom, pair[1], pair[0])
                located = [c for c in claims if "in_area" in c]
                area_check = {
                    "area": state.area.label,
                    "kind": state.area.kind,
                    "source": state.area.source,
                    "chips_inside": sum(state.chip_checks.values()),
                    "chips_total": len(state.chip_checks),
                    "claims_inside": sum(1 for c in located if c["in_area"]),
                    "claims_located": len(located),
                    "chips": state.chip_checks,
                    "claims": located,
                }
                (Path(cfg["out_dir"]) / plan.run_id / "area_check.json").write_text(
                    json.dumps(area_check, indent=1), encoding="utf-8"
                )
            state.final = {
                "type": "done",
                "status": outcome.status,
                "error": outcome.error,
                "claims": claims,
                "area_check": area_check,
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
                sent_area = False
                while True:
                    if not sent_area and state.area_event is not None:
                        self.wfile.write(f"data: {json.dumps(state.area_event)}\n\n".encode())
                        sent_area = True
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
                            state.annotate(ev)
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
