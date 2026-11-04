"""Read-only UI demo using explicitly synthetic evidence; no AWS or model calls.

Run: uv run python -m scripts.demo_evals
"""

from pathlib import Path

import uvicorn
from fastapi.responses import JSONResponse, Response

from analysis import report
from harness.manifest import Index
from harness.web.app import create_app
from tests.test_conditions import save
from tests.test_explain import judged
from tests.test_judging import lgnd_run
from tests.test_web import cfg_for


def app():
    root = Path("out/eval-demo").resolve()
    root.mkdir(parents=True, exist_ok=True)
    cfg = cfg_for(root)
    run = lgnd_run(root / "archive")
    run.__dict__["prompt"] = (
        "SYNTHETIC DEMO: data centers within 10 miles of a protected natural area in Testville"
    )
    run.manifest["prompt"] = run.prompt
    import json

    run.store.write_text(f"runs/{run.run_id}/run.json", json.dumps(run.manifest))
    save(run)
    run, _ = judged(run)
    record = run.judgement
    record["rubric"]["version"] = record["rubric"]["snapshot"]["version"]
    record["value_matcher_version"] = 2
    run.store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(record))
    Index(cfg["out_dir"]).record_run(run.run_id, run.store.uri)
    path = Path(cfg["out_dir"]) / run.run_id / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.render_run(report.analyze(run), "synthetic demo"))
    web = create_app(cfg)

    @web.middleware("http")
    async def readonly(request, call_next):
        if request.method not in ("GET", "HEAD"):
            return JSONResponse(
                {"detail": "Synthetic demo is read-only. No live AWS actions."}, status_code=403
            )
        if request.url.path.startswith("/tiles/"):
            return Response(status_code=404)  # demo has no real satellite imagery
        return await call_next(request)

    return web


if __name__ == "__main__":
    uvicorn.run(app(), host="127.0.0.1", port=8789)
