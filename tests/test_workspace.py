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
