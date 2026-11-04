"""`harness ui`: the Team Foundry console, a FastAPI app (T99) over the archive and the live-run streams."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analysis.trace import ArchiveError, Run
from core.store import open_store
from harness import config as config_mod
from harness import invoke, rows
from harness.manifest import Index
from harness.web import live
from harness.web.api_docs import (
    DESCRIPTION,
    ERRORS,
    EVENTS_DOC,
    TAGS,
    JudgeStarted,
    ModelsResponse,
    RunRequest,
    RunsResponse,
    RunStarted,
)
from harness.web.view import run_row, run_view

HERE = Path(__file__).parent
TEAM = "Team Foundry"


def create_app(cfg: config_mod.Config) -> FastAPI:
    index = Index(cfg["out_dir"])
    app = FastAPI(
        title=f"{TEAM} console API",
        version="1",
        summary="Run the agent, stream its trace, and score each run with the judge tribunal.",
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url="/api/docs",
        redoc_url=None,
    )
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

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def console(request: Request) -> HTMLResponse:
        return page(request, "run.html", run_id=None, active="console")

    @app.get("/runs", response_class=HTMLResponse, include_in_schema=False)
    def runs_page(request: Request) -> HTMLResponse:
        return page(request, "runs.html", active="runs")

    @app.get("/runs/{run_id}", response_class=HTMLResponse, include_in_schema=False)
    def run_page(request: Request, run_id: str) -> HTMLResponse:
        load(run_id)
        return page(request, "run.html", run_id=run_id, active="runs")

    @app.get("/api/models", tags=["Setup"], response_model=ModelsResponse,
             summary="Agent models and the seated judges")  # fmt: skip
    def models() -> dict[str, Any]:
        """The agent models a run can use (`model` in **Start a run**), and the judge tribunal from
        `harness.yaml`. On a run whose agent shares a judge's model family, that judge recuses and a reserve
        sits; the seats actually used are in each run's scorecard."""
        return {"models": agent_models(), "judges": (cfg.get("judging") or {}).get("panel", [])}

    def row_for(run_id: str, uri: str) -> dict[str, Any] | None:
        """A run's row: the saved out/<id>/row.json (harness/rows.py), else built from the archive."""
        state = live.RUNS.get(run_id)
        if state is None or state.done:
            saved = rows.load(cfg["out_dir"], run_id)
            if saved is not None:
                return saved
        try:
            run = Run.load(open_store(uri), run_id)
            return rows.save(cfg["out_dir"], run) if state is None or state.done else run_row(run)
        except Exception:  # noqa: BLE001 - one bad archive shouldn't hide the rest
            return None

    def all_rows() -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=16) as pool:
            out = [r for r in pool.map(lambda kv: row_for(*kv), index.runs().items()) if r]
        out.sort(key=_order_key, reverse=True)
        return out

    # Build any missing rows (older runs, or runs from another machine) in the background at startup, so the
    # first visit to the runs page doesn't wait on S3.
    threading.Thread(target=lambda: _quietly(all_rows), name="rows-warmup", daemon=True).start()

    @app.get("/api/runs", tags=["Runs"], response_model=RunsResponse, summary="List archived runs",
             responses={400: ERRORS[400]})  # fmt: skip
    def list_runs(
        limit: int = Query(50, ge=1, le=200, description="Runs per page."),
        before: str | None = Query(None, description="The `next` cursor from the previous page. Omit it "
                                   "for the newest runs."),
        model: str | None = Query(None, description="Only runs by this agent model key, e.g. `kimi`."),
        verdict: str | None = Query(None, description="Only runs with this verdict: `scored`, `FAILED`, "
                                    "`not scored` or `not judged`."),
    ) -> dict[str, Any]:  # fmt: skip
        """Archived runs, newest first, one summary row each: the score and verdict, the confidence
        label, agent and judging cost, tool calls, errors and runtime.

        **Paging** uses a cursor, so a run that starts while you page doesn't shift the pages. Pass the
        response's `next` as `before` to get the following page; `next` is null on the last page. `total`
        counts every run that matches the filters. Rows are read from `out/<id>/row.json`, rewritten
        whenever the run is judged or replayed."""
        out = all_rows()
        if model:
            out = [r for r in out if r.get("model_key") == model]
        if verdict:
            out = [r for r in out if r.get("verdict") == verdict]
        total = len(out)
        if before:
            cursor = _decode_cursor(before)
            out = [r for r in out if _order_key(r) < cursor]
        page = out[:limit]
        more = len(out) > limit
        return {"runs": page, "next": _encode_cursor(_order_key(page[-1])) if more else None, "total": total}

    @app.get("/api/runs/{run_id}", tags=["Runs"], summary="One run, in full", responses={404: ERRORS[404]})
    def get_run(run_id: str) -> dict[str, Any]:
        """Everything the run page shows, built from the archive alone (so it replays identically):
        `run` (prompt, model, area), `kpis` (score, cost, tool calls, claims verified and inside the area,
        judge agreement), `timeline` (each step in plain English, with the raw span), `map` (GeoJSON:
        the requested boundary, result footprints, claimed sites), `scorecard` (every criterion, each judge's
        vote and rationale, the seats, failure modes), `claims`, `final_answer`, `narrative` and
        `trouble_spots`."""
        return run_view(load(run_id))

    @app.post("/api/runs", tags=["Runs"], response_model=RunStarted, summary="Start a run",
              responses={400: ERRORS[400]})  # fmt: skip
    def post_run(body: RunRequest) -> Any:
        """Start the agent on a prompt, in the background. The search area is read from the prompt and
        resolved to an official boundary first. Follow progress at **Stream a run's events**; when the run
        ends it is judged automatically (`judging.auto`), and the final event carries the full run view."""
        prompt = body.prompt.strip()
        if not prompt:
            return JSONResponse({"error": "Type a prompt first."}, status_code=400)
        try:
            return {"run_id": live.start_run(cfg, index, prompt, body.model or "")}
        except invoke.RunRefused as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.post("/api/runs/{run_id}/judge", tags=["Judging"], response_model=JudgeStarted,
              summary="Judge a run again", responses={404: ERRORS[404], 409: ERRORS[409]})  # fmt: skip
    def post_judge(run_id: str) -> dict[str, Any]:
        """Send an archived run to the judge tribunal again (for example after changing the rubric or the
        panel). The new judgement replaces the old one in the archive. Progress streams at the returned
        `events` URL. A run whose model calls all failed is recorded as **not scored**, at no cost."""
        load(run_id)
        state = live.RUNS.get(run_id)
        if state is not None and not state.done:
            raise HTTPException(409, "this run is still running or being judged")
        live.rejudge(cfg, index, run_id)
        return {"run_id": run_id, "events": f"/api/runs/{run_id}/events"}

    @app.get("/api/runs/{run_id}/events", tags=["Live events"], summary="Stream a run's events",
             description=EVENTS_DOC, response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}}}, 404: ERRORS[404]})  # fmt: skip
    async def events(run_id: str) -> StreamingResponse:
        state = live.RUNS.get(run_id)
        if state is None:
            raise HTTPException(404, "no live run with that ID")
        return StreamingResponse(stream(state), media_type="text/event-stream",
                                 headers={"cache-control": "no-cache"})  # fmt: skip

    @app.get("/reports/{run_id}", response_class=HTMLResponse, tags=["Reports"],
             summary="A run's static HTML report", responses={404: ERRORS[404]})  # fmt: skip
    def report(run_id: str) -> FileResponse:
        """The self-contained report written when the run finished or was last judged
        (`out/<id>/report.html`): the timeline, workflow signals, claim provenance, the panel score with
        every vote, and the answer."""
        path = Path(cfg["out_dir"]) / run_id / "report.html"
        if "/" in run_id or ".." in run_id or not path.is_file():
            raise HTTPException(404, "no report for that run")
        return FileResponse(path, media_type="text/html")

    return app


def _order_key(row: dict[str, Any]) -> tuple[str, str]:
    """Newest first, ties broken by run ID so every row has one place in the order."""
    return (str(row.get("started_at") or ""), str(row.get("id") or ""))


def _encode_cursor(key: tuple[str, str]) -> str:
    return base64.urlsafe_b64encode(json.dumps(list(key)).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if isinstance(raw, list) and len(raw) == 2 and all(isinstance(x, str) for x in raw):
            return (raw[0], raw[1])
    except (ValueError, binascii.Error):
        pass
    raise HTTPException(400, "invalid cursor: pass the `next` value from the previous page")


def _quietly(fn: Any) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 - a warm-up; the request path builds rows on its own
        pass


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
