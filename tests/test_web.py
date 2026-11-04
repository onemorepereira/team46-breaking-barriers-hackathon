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
    assert chips[0]["properties"]["tile_url"].startswith(
        "/tiles/chip/naip/"
    )  # through the console (tile-cache AC2)
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
    judge_only = client.post("/api/runs", json={"prompt": "x", "model": "judge-only"})  # agent: false
    assert judge_only.status_code == 400 and "not an agent model" in judge_only.json()["error"]


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


def test_example_cards_cover_every_continent_with_asia_first_and_are_served():
    """docs/example-cards AC1, AC6: data, not code; six continents; Asia has the most; prompts unique."""
    data = json.loads((Path(__file__).parents[1] / "harness/web/static/examples.json").read_text())
    continents, examples = data["continents"], data["examples"]
    assert continents[0] == "Asia" and len(continents) == 6
    keys = {"continent", "country", "task", "place", "theme", "icon", "prompt"}
    assert all(set(x) == keys and all(isinstance(x[k], str) and x[k] for k in keys) for x in examples)
    assert {x["continent"] for x in examples} == set(continents)
    asia = [x for x in examples if x["continent"] == "Asia"]
    assert len(asia) >= 8 and len(asia) > len(examples) / 2
    assert len({x["prompt"] for x in examples}) == len(examples)
    icons = (
        Path(__file__).parents[1] / "harness/web/static/vendor/tabler-icons/tabler-icons.min.css"
    ).read_text()
    assert all(f".ti-{x['icon']}:before" in icons for x in examples)  # every icon is in the vendored font


def test_runs_list_reads_saved_rows_and_reports_keep_them_current(tmp_path, monkeypatch):
    """The runs table reads out/<id>/row.json; re-judging (via write_report) rewrites it."""
    from harness import rows
    from harness.cli import write_report

    cfg = cfg_for(tmp_path)
    run = lgnd_run(tmp_path / "archive")
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    write_report(cfg, run)
    saved = rows.load(cfg["out_dir"], run.run_id)
    assert saved is not None and saved["verdict"] == "not judged"

    def no_archive(*a, **k):
        raise AssertionError("the runs list re-read an archive it already had a row for")

    client = TestClient(create_app(cfg))
    monkeypatch.setattr("harness.web.app.Run.load", no_archive)
    assert client.get("/api/runs").json()["runs"][0]["id"] == run.run_id

    (tmp_path / "out" / run.run_id / "row.json").write_text('{"version": 0, "row": {}}')  # an older shape
    assert rows.load(cfg["out_dir"], run.run_id) is None


def test_api_docs_explain_every_endpoint_and_hide_the_pages(tmp_path):
    spec = TestClient(create_app(cfg_for(tmp_path))).get("/openapi.json").json()
    assert "tribunal" in spec["info"]["description"] and {t["name"] for t in spec["tags"]} >= {
        "Runs",
        "Judging",
    }
    assert "/" not in spec["paths"] and "/runs" not in spec["paths"] and "/runs/{run_id}" not in spec["paths"]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary") and op.get("description") and op.get("tags"), (method, path)
    row = spec["components"]["schemas"]["RunRow"]["properties"]
    assert "description" in row["verdict"] and "description" in row["confidence"]
    assert "not_scored" in spec["paths"]["/api/runs/{run_id}/events"]["get"]["description"]


def test_runs_list_pages_by_cursor_filters_and_is_stable_when_a_run_starts(tmp_path):
    from harness import rows

    cfg = cfg_for(tmp_path)
    index = Index(cfg["out_dir"])

    def add(i, model="sonnet", verdict="scored", started=None):
        rid = f"run-{i:03d}"
        row = {"id": rid, "started_at": started or f"2026-11-04T10:{i:02d}:00Z", "model_key": model,
               "status": "ok", "prompt": "p", "prompt_file": None, "score": 90.0, "verdict": verdict,
               "not_scored_cause": None, "confidence": "High", "cost_usd": 0.1, "judging_cost_usd": 0.1,
               "tool_calls": 2, "errors": 0, "runtime_s": 10.0, "area": None}  # fmt: skip
        p = tmp_path / "out" / rid / "row.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"version": rows.ROW_VERSION, "row": row}))
        index.record_run(rid, f"file://{tmp_path}/archive")

    for i in range(7):
        add(i, model="kimi" if i % 2 else "sonnet", verdict="FAILED" if i == 3 else "scored")
    add(7, started="2026-11-04T10:06:00Z")  # same start time as run-006: the ID breaks the tie
    client = TestClient(create_app(cfg))

    first = client.get("/api/runs?limit=3").json()
    assert [r["id"] for r in first["runs"]] == ["run-007", "run-006", "run-005"] and first["total"] == 8
    add(50, started="2026-11-04T11:00:00Z")  # a run starts while someone pages
    seen, nxt = [r["id"] for r in first["runs"]], first["next"]
    while nxt:
        page = client.get(f"/api/runs?limit=3&before={nxt}").json()
        seen += [r["id"] for r in page["runs"]]
        nxt = page["next"]
    assert seen == ["run-007", "run-006", "run-005", "run-004", "run-003", "run-002", "run-001", "run-000"]

    kimi = client.get("/api/runs?model=kimi").json()
    assert [r["id"] for r in kimi["runs"]] == ["run-005", "run-003", "run-001"] and kimi["next"] is None
    assert [r["id"] for r in client.get("/api/runs?verdict=FAILED").json()["runs"]] == ["run-003"]
    assert client.get("/api/runs?before=not-a-cursor").status_code == 400
    assert (
        client.get("/api/runs?limit=0").status_code == 422
        and client.get("/api/runs?limit=201").status_code == 422
    )


def test_tile_routes_validate_cache_and_document(tmp_path, monkeypatch):
    """docs/tile-cache AC2, AC4, AC5, AC8, AC9, AC10 through create_app; only the provider is faked."""
    from harness import tiles

    calls, reply = [], {"data": b"\xff\xd8\xff\xe0tile"}

    def fake(url):
        calls.append(url)
        if isinstance(reply["data"], Exception):
            raise reply["data"]
        return reply["data"]

    monkeypatch.setattr(tiles, "fetch_upstream", fake)
    cfg = cfg_for(tmp_path)
    run = lgnd_run(tmp_path / "archive")
    Index(cfg["out_dir"]).record_run(run.run_id, f"file://{tmp_path}/archive")
    client = TestClient(create_app(cfg))

    bad_urls = [
        "/tiles/base/osm/1/0/0.jpg",  # OSM is never proxied
        "/tiles/base/s2/16/0/0.jpg",  # above Sentinel-2's max zoom
        "/tiles/base/naip/2/4/0.jpg",  # x out of range
        "/tiles/chip/x/0,0,0.1,0.1.jpg",  # unknown index
        "/tiles/chip/s2/0,0,3,0.1.jpg",  # wider than 2 degrees
        "/tiles/chip/s2/nope.jpg",  # not a bbox
    ]
    for bad in bad_urls:
        assert client.get(bad).status_code == 404, bad
    assert calls == []  # nothing invalid ever reached a provider

    first = client.get("/tiles/base/s2/3/1/2.jpg")
    assert first.status_code == 200 and first.headers["x-tile-origin"] == "upstream"
    assert (
        first.headers["cache-control"] == "public, max-age=604800"
        and first.headers["content-type"] == "image/jpeg"
    )
    warm = client.get("/tiles/base/s2/3/1/2.jpg")
    assert warm.headers["x-tile-origin"] == "cache" and len(calls) == 1  # AC8: a warm hit makes no fetch

    view = client.get(f"/api/runs/{run.run_id}").json()
    chip = view["map"]["chips"]["features"][0]["properties"]
    assert chip["tile_url"].startswith("/tiles/chip/") and f"run={run.run_id}" in chip["tile_url"]
    assert chip["tile_source"]  # AC9: attribution travels with the tile
    reply["data"] = OSError("provider down")
    assert client.get("/tiles/chip/s2/1,1,1.1,1.1.jpg").status_code == 502  # nothing anywhere
    run.store.write_bytes(tiles.archive_key(run.run_id, "s2", [1.0, 1.0, 1.1, 1.1]), b"\x89PNGarchived")
    archived = client.get(f"/tiles/chip/s2/1,1,1.1,1.1.jpg?run={run.run_id}")
    assert archived.headers["x-tile-origin"] == "archive" and archived.headers["content-type"] == "image/png"

    home = client.get("/").text
    assert 'data-tile-proxy="1"' in home
    js = (STATIC / "app.js").read_text()
    for credit in ["EOX", "USGS The National Map", "OpenStreetMap contributors"]:
        assert credit in js  # AC9: basemap attributions unchanged
    spec = client.get("/openapi.json").json()
    for path in ["/tiles/base/{source}/{z}/{x}/{y}.jpg", "/tiles/chip/{idx}/{bbox}.jpg"]:
        assert spec["paths"][path]["get"]["tags"] == ["Tiles"]  # AC10

    off = TestClient(create_app(cfg_for(tmp_path, tiles={"serve": False})))  # rollback lever
    assert 'data-tile-proxy="0"' in off.get("/").text
    url = off.get(f"/api/runs/{run.run_id}").json()["map"]["chips"]["features"][0]["properties"]["tile_url"]
    assert url.startswith("https://")


def test_console_is_dark_and_map_details_dock_instead_of_popping_up(tmp_path):
    """docs/console-polish AC1, AC2, AC5, structure only; tests/browser/console_probe.py measures behavior."""
    client = TestClient(create_app(cfg_for(tmp_path)))
    for page in ["/", "/runs"]:
        html = client.get(page).text
        assert (
            '<html lang="en" data-bs-theme="dark">' in html and 'name="color-scheme" content="dark"' in html
        )
    docs = client.get("/api/docs")  # the console's own header, with the reference framed below it
    assert docs.status_code == 200 and 'data-bs-theme="dark"' in docs.text
    assert 'src="/api/reference"' in docs.text
    ref = client.get("/api/reference").text  # Scalar alone (pinned, SRI), with no Tabler to leak into it
    assert "@scalar/api-reference@1.75.0/" in ref and 'integrity="sha384-' in ref and "tabler" not in ref
    assert 'id="foundry-api"' in ref and 'id="api-reference"' not in ref
    cfg_js = (STATIC / "api-docs.js").read_text()
    for setting in [
        'url: "/openapi.json"',
        'forceDarkModeState: "dark"',
        "telemetry: false",
        "agent: { disabled: true }",
    ]:
        assert setting in cfg_js, setting
    js = (STATIC / "app.js").read_text()
    assert "maplibregl.Popup" not in js and "cooperativeGestures: true" in js and "scrollIntoView" in js
    assert js.count("scrollIntoView") == 1  # only the toast's Show button may move the page
    home = client.get("/").text
    assert (
        'id="detail" role="region" aria-label="Result details"' in home
        and 'role="status" aria-live="polite"' in home
    )
    report_css = (REPO / "analysis/templates/_style.html").read_text()
    assert "color-scheme:dark" in report_css and "prefers-color-scheme" not in report_css
