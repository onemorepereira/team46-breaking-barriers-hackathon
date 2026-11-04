"""The Team Foundry console (docs/judging/spec.md AC10-AC14).

FastAPI endpoints, the live stream of a scripted run, the plain-language timeline, the run view's KPIs and map
layers, and offline rendering of archived runs.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from analysis import timeline
from analysis.trace import Run
from harness import config as config_mod
from harness.manifest import Index
from harness.web.app import create_app
from harness.web.live import span_event
from harness.web.view import run_view
from tests.test_judging import CFG, FakeBedrock, lgnd_run

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "harness/web/static"


def cfg_for(tmp_path, **extra):
    raw = {
        "archive_uri": f"file://{tmp_path}/archive",
        "local_archive_uri": f"file://{tmp_path}/archive",
        "out_dir": str(tmp_path / "out"),
        "models": {
            "scripted": {"id": "scripted", "max_tokens": 1000},
            "judge-only": {"id": "j", "agent": False},
        },
        "prices_per_mtok": {"scripted": {"in": 1.0, "out": 5.0}},
        **extra,
    }
    p = tmp_path / "h.yaml"
    p.write_text(json.dumps(raw))
    return config_mod.load(str(p))


# ---------- AC11 plain-language timeline ----------
def test_timeline_sentences_are_plain_english(tmp_path):
    run = lgnd_run(tmp_path)
    entries = timeline.entries(run.spans)
    by = {e.ref: e for e in entries}
    assert by["start"].sentence == "The agent started with AWS Open Data (RODA) (2 tools)."
    assert by["M1"].sentence.startswith("Decided to call search_place_find.")
    assert by["T1"].sentence == (
        "Searched NAIP aerial imagery (US) for 'data center' inside a 5-point boundary: 2 matches, "
        "best similarity 0.31."
    )
    assert by["M2"].sentence.startswith("Wrote the final answer. Found one data center")
    assert by["end"].sentence == "The run finished normally."
    assert (
        by["T1"].raw["attributes"]["harness.tool.name"] == "search_place_find"
    )  # the raw span, one click away


def test_live_span_event_carries_entry_and_chips():
    span = {
        "name": "harness.tool_result",
        "context": {"span_id": "0xabc"},
        "attributes": {
            "harness.tool.server": "lgnd",
            "harness.tool.name": "search_place_find",
            "harness.tool.ref": "T4",
            "harness.tool.status": "success",
            "harness.tool.arguments": json.dumps({"scope": {"index": "s2"}}),
            "harness.tool.result": json.dumps(
                {
                    "where": "everywhere",
                    "matches": {
                        "columns": ["node", "lat", "lon", "bbox"],
                        "rows": [["s2/obs:1", 17.5, 105.2, [105.1, 17.4, 105.3, 17.6]]],
                    },
                }
            ),
        },
    }
    ev = span_event(span)
    assert ev["type"] == "step" and ev["entry"]["ref"] == "T4" and ev["entry"]["results"] == 1
    assert "everywhere (no area given)" in ev["entry"]["sentence"]
    assert ev["chips"][0]["ref"] == "T4"
    assert span_event({"name": "chat", "attributes": {}}) is None


# ---------- AC12 / AC13 run view ----------
def test_run_view_kpis_map_and_scorecard(tmp_path):
    from harness import judge

    run = lgnd_run(tmp_path)
    judge.judge_run(CFG, run, run.store, client=FakeBedrock({}))
    v = run_view(Run.load(run.store, run.run_id))
    k = v["kpis"]
    assert k["score"] is not None and k["confidence"] in ("High", "Medium", "Low")
    assert (k["claims_matched"], k["claims_total"], k["claims_inside"], k["claims_located"]) == (2, 2, 1, 2)
    assert (k["chips_inside"], k["chips_total"], k["tool_calls"], k["model_calls"]) == (1, 2, 1, 2)
    assert k["agent_cost_usd"] is not None and k["judging_cost_usd"] > 0
    chips = v["map"]["chips"]["features"]
    assert len(chips) == 2 and {c["properties"]["inside"] for c in chips} == {True, False}
    assert chips[0]["properties"]["tile_url"].startswith("https://imagery.nationalmap.gov/")
    assert v["map"]["area"]["properties"]["label"] == "Testville"
    assert len(v["map"]["claims"]["features"]) == 2
    t1 = next(e for e in v["timeline"] if e["ref"] == "T1")
    assert t1["bounds"] and t1["results"] == 2
    card = v["scorecard"]
    assert len(card["judges"]) == 5 and card["seats"][0]["recused_for"] == "opus"
    assert {c["id"] for c in card["criteria"]} >= {"grounding", "claim_provenance"}


# ---------- AC10 / AC14 endpoints ----------
def test_pages_assets_and_archive_endpoints_render_offline(tmp_path):
    cfg = cfg_for(tmp_path)
    run = lgnd_run(tmp_path / "archive")
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    client = TestClient(create_app(cfg))
    home = client.get("/")
    assert home.status_code == 200 and "Team Foundry" in home.text and "foundry-mark.png" in home.text
    assert "cdn." not in home.text and "unpkg" not in home.text  # vendored assets only (AC14)
    for asset in [
        "vendor/tabler/tabler.min.css",
        "vendor/maplibre/maplibre-gl.js",
        "vendor/marked/marked.umd.js",
        "vendor/dompurify/purify.min.js",
        "app.js",
        "favicon.png",
    ]:
        assert client.get(f"/static/{asset}").status_code == 200, asset
    assert client.get("/api/models").json()["models"] == ["scripted"]  # judges aren't offered as agents
    rows = client.get("/api/runs").json()["runs"]
    assert rows[0]["id"] == run.run_id and rows[0]["verdict"] == "not judged" and rows[0]["tool_calls"] == 1
    assert client.get(f"/runs/{run.run_id}").status_code == 200
    assert client.get(f"/api/runs/{run.run_id}").json()["kpis"]["claims_total"] == 2
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/reports/..%2Fetc").status_code == 404
    assert client.post("/api/runs", json={"prompt": "  "}).status_code == 400
    assert client.post("/api/runs", json={"prompt": "x", "model": "unknown"}).status_code == 400


def test_scripted_run_streams_steps_then_the_full_view(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TEST_SCRIPT", str(REPO / "tests/fixtures/scripted_run.json"))
    client = TestClient(create_app(cfg_for(tmp_path)))
    run_id = client.post("/api/runs", json={"prompt": "Find DA11", "model": "scripted"}).json()["run_id"]
    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "done":
                    break
    types = [e["type"] for e in events]
    assert types[0] == "area" and types[-1] == "done" and "step" in types
    kinds = [e["entry"]["kind"] for e in events if e["type"] == "step"]
    assert kinds[0] == "start" and "model" in kinds and "tool" in kinds and kinds[-1] == "end"
    done = events[-1]
    assert done["status"] == "ok" and done["view"]["kpis"]["missing_fields"] == 0
    assert [c["status"] for c in done["view"]["claims"]] == ["matched", "matched"]
    assert "Run report" in client.get(f"/reports/{run_id}").text


def test_rejudge_endpoint_streams_the_panel_and_refreshes_the_view(tmp_path, monkeypatch):
    from harness import judge
    from tests.test_judging import CFG

    cfg = cfg_for(
        tmp_path,
        models={**CFG["models"], "scripted": {"id": "scripted"}},
        prices_per_mtok=CFG["prices_per_mtok"],
        judging=CFG["judging"],
    )
    run = lgnd_run(tmp_path / "archive")
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    monkeypatch.setattr(judge, "_bedrock", lambda cfg: FakeBedrock({}))
    client = TestClient(create_app(cfg))
    assert client.post(f"/api/runs/{run.run_id}/judge").status_code == 200
    events = []
    with client.stream("GET", f"/api/runs/{run.run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "done":
                    break
    types = [e["type"] for e in events]
    assert types[0] == "rejudge" and "judging" in types and types.count("judge") == 5
    assert events[-1]["view"]["scorecard"]["valid_judges"] == [5]
    assert client.get("/api/runs").json()["runs"][0]["verdict"] == "scored"  # the cached row was refreshed
