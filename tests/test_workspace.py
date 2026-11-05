"""The built frontend shares the backend origin and cannot escape its asset directory."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from harness.web.app import create_app
from tests.test_web import cfg_for


def test_workspace_and_built_assets_are_served_without_node(tmp_path):
    client = TestClient(create_app(cfg_for(tmp_path)))
    response = client.get("/workspace", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "workspace/"
    page = client.get("/workspace/")
    assert page.status_code == 200
    assert "Team Foundry" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assets = re.findall(r'(?:src|href)="(\./assets/[^"]+)"', page.text)
    assert len(assets) >= 2
    for path in assets:
        result = client.get("/workspace/" + path.removeprefix("./"))
        assert result.status_code == 200
    assert client.get("/workspace/missing.js").status_code == 404
    assert client.get("/workspace/%2e%2e/app.py").status_code == 404


def test_workspace_does_not_replace_existing_api_or_console(tmp_path):
    client = TestClient(create_app(cfg_for(tmp_path)))
    assert client.get("/").status_code == 200
    assert client.get("/api/models").json()["models"] == ["scripted"]
    assert client.get("/api/runs").json()["runs"] == []
    assert client.post("/api/runs", json={"prompt": ""}).status_code == 400


def test_compiled_ui_has_no_prototype_findings_or_external_fallback_data():
    root = Path(__file__).resolve().parents[1] / "harness/web/static/workspace/assets"
    js = "\n".join(p.read_text() for p in root.glob("*.js"))
    assert js
    for fake in (
        "Mymensingh solar candidate",
        "Sirajganj solar candidate",
        "Feni solar candidate",
        "PrototypeSwitcher",
    ):
        assert fake not in js


def test_progress_snapshot_uses_existing_events_without_starting_work(tmp_path, monkeypatch):
    from harness.web import live

    state = live.RunState("ui-test", tmp_path / "missing.jsonl")
    state.area_event = {"type": "area", "label": "Testville"}
    state.push({"type": "judge", "key": "test", "status": "ok"})
    state.done = True
    state.final = {"type": "done", "view": {"run": {"id": "ui-test"}}}
    monkeypatch.setitem(live.RUNS, "ui-test", state)
    client = TestClient(create_app(cfg_for(tmp_path)))
    result = client.get("/api/runs/ui-test/progress").json()
    assert result["done"] is True
    assert [e["type"] for e in result["events"]] == ["area", "judge", "done"]
    assert result["events"][-1]["view"]["run"]["id"] == "ui-test"
    assert client.get("/api/runs/not-live/progress").status_code == 404


def test_progress_cursor_returns_only_new_events_and_done_means_drained(tmp_path, monkeypatch):
    import json

    from harness.web import live

    trace = tmp_path / "live.jsonl"
    trace.write_text("")
    state = live.RunState("ui-cursor", trace)
    state.area_event = {"type": "area", "label": "Testville"}
    monkeypatch.setitem(live.RUNS, "ui-cursor", state)
    client = TestClient(create_app(cfg_for(tmp_path)))
    first = client.get("/api/runs/ui-cursor/progress").json()
    assert [e["type"] for e in first["events"]] == ["area"] and first["done"] is False
    state.push({"type": "judge", "key": "a", "status": "ok"})
    second = client.get(f"/api/runs/ui-cursor/progress?cursor={first['cursor']}").json()
    assert [e["type"] for e in second["events"]] == ["judge"]  # no repeat of the area event
    third = client.get(f"/api/runs/ui-cursor/progress?cursor={second['cursor']}").json()
    assert third["events"] == [] and third["cursor"] == second["cursor"]
    state.push({"type": "judge", "key": "b", "status": "ok"})
    state.done = True
    state.final = {"type": "done"}
    last = client.get(f"/api/runs/ui-cursor/progress?cursor={third['cursor']}").json()
    assert [e["type"] for e in last["events"]] == ["judge", "done"] and last["done"] is True
    assert client.get("/api/runs/ui-cursor/progress?cursor=nope").status_code == 400
    del json


def test_progress_reads_done_before_events(tmp_path, monkeypatch):
    """A worker that writes its last event and sets done between our reads must not be reported
    done without that event (the reply would then end the client's polling)."""
    from harness.web import app as app_mod
    from harness.web import live

    trace = tmp_path / "live.jsonl"
    trace.write_text("")
    state = live.RunState("ui-race", trace)
    monkeypatch.setitem(live.RUNS, "ui-race", state)
    real = live.read_new

    def racing_read(st, pos):
        out = real(st, pos)
        st.push({"type": "judge", "key": "late", "status": "ok"})  # lands after we read the file...
        st.done, st.final = True, {"type": "done"}  # ...and the run ends
        return out

    monkeypatch.setattr(app_mod.live, "read_new", racing_read)
    client = TestClient(create_app(cfg_for(tmp_path)))
    first = client.get("/api/runs/ui-race/progress").json()
    assert first["done"] is False  # done was read before the run ended, so this poll can't claim it
    monkeypatch.setattr(app_mod.live, "read_new", real)
    nxt = client.get(f"/api/runs/ui-race/progress?cursor={first['cursor']}").json()
    seen = [e["type"] for e in first["events"] + nxt["events"]]
    assert seen == ["judge", "done"] and nxt["done"] is True  # every event once, done last


def test_guidance_progress_drains_the_existing_job_once(tmp_path, monkeypatch):
    from harness.web import live

    state = live.RunState("guidance-1", tmp_path / "missing.jsonl")
    state.push({"type": "evaluating", "done": 1, "total": 5})
    monkeypatch.setitem(live.GUIDANCE_JOBS, 1, state)
    client = TestClient(create_app(cfg_for(tmp_path)))
    first = client.get("/api/guidance/1/progress").json()
    assert first["done"] is False and len(first["events"]) == 1
    assert client.get(f"/api/guidance/1/progress?cursor={first['cursor']}").json()["events"] == []
    state.push({"type": "evaluated", "verdict": "insufficient_evidence"})
    state.done, state.final = True, {"type": "done", "report": {"verdict": "insufficient_evidence"}}
    last = client.get(f"/api/guidance/1/progress?cursor={first['cursor']}").json()
    assert [e["type"] for e in last["events"]] == ["evaluated", "done"] and last["done"] is True
    assert client.get("/api/guidance/9/progress").status_code == 404
