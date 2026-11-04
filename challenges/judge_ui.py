"""Private workshop proof page. Never serves OAuth secrets or bearer tokens."""

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from challenges.proof import ROOT, run

app = FastAPI(title="Team46 tiered challenge proof")
PAGE = Path(__file__).with_name("judge.html").read_text()


@app.get("/")
def page():
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})


@app.get("/state")
def state():
    p = ROOT / "resources.json"
    data = json.loads(p.read_text()) if p.exists() else {}
    safe = {k: v for k, v in data.items() if k not in ["client_secret"]}
    q = ROOT / "proof.json"
    return {"resources": safe, "proof": json.loads(q.read_text()) if q.exists() else None}


@app.post("/proof")
def proof():
    try:
        return run()
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=503)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8790, log_level="warning")
