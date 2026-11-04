"""`harness ui`: the Team Foundry console, a FastAPI app (T99) over the archive and the live-run streams."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analysis.trace import ArchiveError, Run
from core.store import open_store
from harness import config as config_mod
from harness import invoke
from harness.manifest import Index
from harness.web import live
from harness.web.view import run_row, run_view

HERE = Path(__file__).parent
TEAM = "Team Foundry"


def create_app(cfg: config_mod.Config) -> FastAPI:
    index = Index(cfg["out_dir"])
    app = FastAPI(title=f"{TEAM} console", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    pages = Jinja2Templates(directory=HERE / "templates")

    def load(run_id: str) -> Run:
        if "/" in run_id or ".." in run_id:
            raise HTTPException(404, "unknown run")
        try:
            return Run.load(open_store(index.run_uri(run_id) or cfg["archive_uri"]), run_id)
        except ArchiveError as e:
            raise HTTPException(404, str(e)) from e

    def agent_models() -> list[str]:
        return [k for k, m in (cfg["models"] or {}).items() if m.get("agent", True)]

    def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        return pages.TemplateResponse(request, name, {"team": TEAM, "models": agent_models(), **ctx})

    @app.get("/", response_class=HTMLResponse)
    def console(request: Request) -> HTMLResponse:
        return page(request, "run.html", run_id=None, active="console")

    @app.get("/runs", response_class=HTMLResponse)
    def runs_page(request: Request) -> HTMLResponse:
        return page(request, "runs.html", active="runs")

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_page(request: Request, run_id: str) -> HTMLResponse:
        load(run_id)
        return page(request, "run.html", run_id=run_id, active="runs")

    @app.get("/api/models")
    def models() -> dict[str, Any]:
        return {"models": agent_models(), "judges": (cfg.get("judging") or {}).get("panel", [])}

    @app.get("/api/runs")
    def list_runs() -> dict[str, Any]:
        rows = []
        for run_id, uri in index.runs().items():
            if uri.startswith("s3://") and not cfg.get("ui_list_s3", True):
                continue
            try:
                rows.append(run_row(Run.load(open_store(uri), run_id)))
            except Exception:  # noqa: BLE001 - one bad archive shouldn't hide the rest
                continue
        rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
        return {"runs": rows}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return run_view(load(run_id))

    @app.post("/api/runs")
    async def post_run(request: Request) -> JSONResponse:
        body = await request.json()
        prompt, model = str(body.get("prompt", "")).strip(), str(body.get("model", ""))
        if not prompt:
            return JSONResponse({"error": "Type a prompt first."}, status_code=400)
        try:
            return JSONResponse({"run_id": live.start_run(cfg, index, prompt, model)})
        except invoke.RunRefused as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.post("/api/runs/{run_id}/judge")
    def post_judge(run_id: str) -> dict[str, Any]:
        load(run_id)
        state = live.RUNS.get(run_id)
        if state is not None and not state.done:
            raise HTTPException(409, "this run is still running or being judged")
        live.rejudge(cfg, index, run_id)
        return {"run_id": run_id, "events": f"/api/runs/{run_id}/events"}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str) -> StreamingResponse:
        state = live.RUNS.get(run_id)
        if state is None:
            raise HTTPException(404, "no live run with that ID")
        return StreamingResponse(stream(state), media_type="text/event-stream",
                                 headers={"cache-control": "no-cache"})  # fmt: skip

    @app.get("/reports/{run_id}", response_class=HTMLResponse)
    def report(run_id: str) -> FileResponse:
        path = Path(cfg["out_dir"]) / run_id / "report.html"
        if "/" in run_id or ".." in run_id or not path.is_file():
            raise HTTPException(404, "no report for that run")
        return FileResponse(path, media_type="text/html")

    return app


def sse(ev: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(ev, default=str)}\n\n".encode()


async def stream(state: live.RunState) -> AsyncIterator[bytes]:
    pos, sent_area, sent_extra = 0, False, 0
    while True:
        if not sent_area and state.area_event is not None:
            yield sse(state.area_event)
            sent_area = True
        evs, pos = live.read_new(state, pos)
        for ev in evs:
            yield sse(ev)
        with state.lock:
            extra = state.extra[sent_extra:]
            sent_extra += len(extra)
        for ev in extra:
            yield sse(ev)
        if state.done and not evs and not extra:
            yield sse(state.final or {"type": "done", "status": "unknown"})
            return
        await asyncio.sleep(0.4)


def serve(cfg: config_mod.Config, port: int) -> int:
    import uvicorn

    print(f"{TEAM} console on http://127.0.0.1:{port}  (Ctrl-C to stop)", flush=True)
    uvicorn.run(create_app(cfg), host="127.0.0.1", port=port, log_level="warning")
    return 0
