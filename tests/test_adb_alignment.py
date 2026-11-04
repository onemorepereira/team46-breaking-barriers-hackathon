"""ADB alignment (docs/adb-alignment/spec.md): ties and snapshots, licences, suite metadata, per-concept and
transfer rows, the USPVDB builder, and the run view and report carrying all of it."""

import io
import json
import zipfile

import pytest

from analysis import licences, report
from analysis import reference as R
from analysis.trace import Run
from harness import reference as H
from tests.fixtures.builder import RunBuilder

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0.009, 0], [0.009, 0.009], [0, 0.009], [0, 0]]]}


def write_set(root, ref_id="t-set", features=None, **over):
    meta = {
        "schema_version": 1,
        "id": ref_id,
        "concept": "solar_farm",
        "place": "Testville",
        "area": SQUARE,
        "completeness": "complete",
        "completeness_note": "all",
        "source": {"name": "test", "version": "1"},
        "licence": {
            "id": "CC-BY-4.0",
            "name": "CC BY 4.0",
            "url": "https://x",
            "attribution": "Test",
            "commercial_use_ok": True,
        },
        "unit": "asset",
        "cell_m": 160,
        **over,
    }
    feats = features or [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0005, 0.0005]},
            "properties": {"ref_id": "a"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.008, 0.008]},
            "properties": {"ref_id": "b"},
        },
    ]
    d = root / ref_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "reference.json").write_text(json.dumps(meta))
    (d / "features.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return d


def claim_run(root, run_id="run-0001", coords=((0.0005, 0.0005),)):
    claims = [
        {"claim": f"site {i}", "value": f"{lat}, {lon}", "ref": "T1"} for i, (lat, lon) in enumerate(coords)
    ]
    answer = "Found.\n```json\n" + json.dumps({"claims": claims}) + "\n```"
    b = RunBuilder(root=root, run_id=run_id)
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "search_place_find", "input": {}})
    result = json.dumps({"results": [{"lat": lat, "lon": lon} for lat, lon in coords]})
    b.tool("search_place_find", {"scope": {"index": "naip", "area": {"ring": []}}}, result)
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model(answer)
    b.run_end()
    b.write(
        final_output=answer,
        search_area={
            "label": "Testville",
            "source": "OpenStreetMap Nominatim, relation 1",
            "geometry": SQUARE,
            "mode": "enforce",
        },
    )
    from core.store import FileStore

    return Run.load(FileStore(f"file://{root}"), run_id)


# ---------- AC1-AC3: ties snapshot the set into the archive ----------
def test_tie_snapshots_the_set_and_scoring_reads_only_the_archive(tmp_path):
    refs = tmp_path / "refs"
    write_set(refs)
    run = claim_run(tmp_path / "archive")
    rec = H.tie(run.store, run.run_id, "t-set", by="cli", root=refs)
    assert (tmp_path / "archive/runs/run-0001/reference/features.geojson").is_file()
    rep = report.analyze(Run.load(run.store, run.run_id), repo_sha=rec["sha256"])
    assert rep.reference["site_recall"] == 0.5 and rep.reference["found"] == ["a"]
    assert rep.reference["stale"] is False
    # rebuilding the repo set never changes the archived run's metrics
    import shutil

    shutil.rmtree(refs / "t-set")
    write_set(
        refs,
        features=[
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.004, 0.004]},
                "properties": {"ref_id": "z"},
            }
        ],
    )
    again = report.analyze(Run.load(run.store, run.run_id), repo_sha=H.repo_sha("t-set", refs))
    assert again.reference["found"] == ["a"] and again.reference["stale"] is True


def test_an_untied_run_has_no_reference_and_a_broken_snapshot_reports_an_error(tmp_path):
    run = claim_run(tmp_path / "archive")
    assert report.analyze(run).reference is None
    run.store.write_text("runs/run-0001/reference/tie.json", json.dumps({"id": "gone"}))
    assert "missing" in report.analyze(Run.load(run.store, run.run_id)).reference["error"]


def test_tie_refuses_a_bad_set_and_a_bad_id(tmp_path):
    refs = tmp_path / "refs"
    write_set(refs, licence={"id": "CC-BY-NC-4.0", "name": "CC BY-NC", "url": "u", "commercial_use_ok": True})
    run = claim_run(tmp_path / "archive")
    with pytest.raises(R.ReferenceError, match="non-commercial"):
        H.tie(run.store, run.run_id, "t-set", by="cli", root=refs)
    with pytest.raises(R.ReferenceError, match="invalid reference id"):
        H.tie(run.store, run.run_id, "../etc", by="cli", root=refs)


def test_licence_filter_matches_whole_tokens_only():
    ok = {"id": "LGND-shared-1", "name": "LGND data licence", "url": "u", "commercial_use_ok": True}
    assert not R.BAD_LICENCE_RE.search(f"{ok['id']} {ok['name']}")
    for bad in (
        "CC-BY-ND-4.0",
        "Creative Commons Attribution-NoDerivatives",
        "NonCommercial use",
        "academic only",
    ):
        assert R.BAD_LICENCE_RE.search(bad), bad


# ---------- AC6-AC7: licences ----------
def test_licences_list_sources_and_mark_lgnd_unknown(tmp_path):
    run = claim_run(tmp_path / "archive")
    lic = licences.for_run(run, None, judges=["opus"], narrative_model="sonnet")
    keys = {i["key"] for i in lic["items"]}
    assert {"lgnd:naip", "lgnd", "boundary:osm", "model:opus", "model:sonnet"} <= keys
    naip = next(i for i in lic["items"] if i["key"] == "lgnd:naip")
    assert naip["licence"] == "Public Domain with Attribution" and naip["presentable"] is True
    assert lic["presentable"] is False and "LGND Geo service" in lic["blockers"][0]


def test_roda_licence_is_read_from_the_archived_tool_result(tmp_path):
    b = RunBuilder(root=tmp_path / "archive")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "preview_dataset", "input": {}})
    b.tool(
        "preview_dataset",
        {"slug": "some-grid"},
        json.dumps(
            {"slug": "some-grid", "license": "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)"}
        ),
    )
    b.lines[-1]["attributes"]["harness.tool.server"] = "roda"
    b.model("done")
    b.run_end()
    b.write(final_output="done")
    from core.store import FileStore

    run = Run.load(FileStore(f"file://{tmp_path}/archive"), "run-0001")
    item = next(i for i in licences.for_run(run)["items"] if i["key"] == "some-grid")
    assert "CC BY 4.0" in item["licence"] and item["presentable"] is True


# ---------- AC9: per concept and transfer ----------
def test_concept_and_transfer_rows_pool_each_role_and_skip_nulls():
    rows = [
        {
            "concept": "warehouse",
            "model_key": "sonnet",
            "role": "home",
            "score": 80.0,
            "site_recall": 0.6,
            "cell_precision": 0.5,
            "count_ratio": 1.2,
        },
        {
            "concept": "warehouse",
            "model_key": "sonnet",
            "role": "transfer",
            "score": 60.0,
            "site_recall": None,
            "cell_precision": None,
            "count_ratio": None,
        },
        {
            "concept": "warehouse",
            "model_key": "sonnet",
            "role": "transfer",
            "score": None,
            "site_recall": None,
            "cell_precision": None,
            "count_ratio": None,
        },
        {
            "concept": None,
            "model_key": "sonnet",
            "role": None,
            "score": 10.0,
            "site_recall": None,
            "cell_precision": None,
            "count_ratio": None,
        },
    ]
    (c,) = report.concept_rows(rows)
    assert c["runs"] == 3 and c["score"] == 70.0 and c["site_recall"] == 0.6
    (t,) = report.transfer_rows(rows)
    assert t["score_gap"] == 20.0 and t["n_home"] == 1 and t["n_transfer"] == 1 and t["recall_gap"] is None
    assert "transfer" in report.concepts_csv(rows)


# ---------- AC5: the USPVDB builder (fixture bytes, no network) ----------
def test_build_uspvdb_filters_one_county_and_writes_a_valid_set(tmp_path):
    feats = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.001, 0.001]},
            "properties": {"case_id": 1, "p_state": "TX", "p_county": "Pecos", "p_name": "A", "p_cap_ac": 50},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5, 5]},
            "properties": {"case_id": 2, "p_state": "TX", "p_county": "Bexar", "p_name": "B"},
        },
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "uspvdb_v4_0_20260414.geojson", json.dumps({"type": "FeatureCollection", "features": feats})
        )
    county = {"type": "Feature", "geometry": SQUARE, "properties": {"NAME": "Pecos County", "GEOID": "48371"}}
    out = H.build_uspvdb("TX", "48", "Pecos", "uspvdb-test", buf.getvalue(), county, root=tmp_path)
    ref = H.load("uspvdb-test", tmp_path)
    assert out["assets"] == 1 and ref.complete and ref.licence["commercial_use_ok"] is True
    assert ref.source["version"] == "4.0 (20260414)" and "GEOID 48371" in ref.meta["area_source"]
    assert (tmp_path / "uspvdb-test/BUILD.md").is_file()


def test_the_shipped_pecos_set_loads_and_is_licence_clean():
    ref = H.load("uspvdb-tx-pecos-v4")
    assert ref.complete and ref.concept == "solar_farm" and len(ref.features) >= 1
    assert ref.licence["commercial_use_ok"] is True and "OpenStreetMap" not in json.dumps(ref.meta)


# ---------- AC8: suite metadata ----------
def test_suite_entries_with_metadata_are_stored_and_tied(tmp_path, monkeypatch):
    from harness import cli, invoke

    suite = tmp_path / "s.yaml"
    pf = tmp_path / "p.md"
    pf.write_text("Find things in Testville.")
    suite.write_text(
        f"suite: s\nmodels: [m]\nbackend: local\nprompts:\n  - {{file: {pf}, concept: solar_farm, "
        f"role: home, reference: uspvdb-tx-pecos-v4}}\n  - {pf}\n"
    )
    seen = []

    def fake_run_one(cfg, index, plan):
        seen.append(
            (plan.manifest.get("suite_meta"), cfg_store.read_text(f"runs/{plan.run_id}/reference/tie.json"))
        )
        return invoke.Outcome("ok", None), "ok"

    from core.store import FileStore
    from harness import config as config_mod

    cfgp = tmp_path / "h.yaml"
    cfgp.write_text(
        json.dumps(
            {
                "local_archive_uri": f"file://{tmp_path}/archive",
                "archive_uri": f"file://{tmp_path}/archive",
                "out_dir": str(tmp_path / "out"),
                "models": {"m": {"id": "m"}},
                "prices_per_mtok": {"m": {"in": 1, "out": 1}},
            }
        )
    )
    cfg = config_mod.load(str(cfgp))
    cfg_store = FileStore(f"file://{tmp_path}/archive")
    monkeypatch.setattr(cli, "_run_one", fake_run_one)
    monkeypatch.setattr(invoke, "worst_case_usd", lambda cfg, m: 0.1)
    from harness.manifest import Index

    args = type("A", (), {"suite": str(suite), "backend": None})()
    cli.cmd_suite(cfg, Index(cfg["out_dir"]), args, "local")
    assert seen[0][0] == {
        "concept": "solar_farm",
        "role": "home",
        "reference": "uspvdb-tx-pecos-v4",
        "task": "T1",
    }
    assert json.loads(seen[0][1])["id"] == "uspvdb-tx-pecos-v4"
    assert seen[1] == (None, None)  # a plain path entry behaves as before


def test_lgnd_tools_without_an_index_fold_into_the_service_and_model_roles_merge(tmp_path):
    b = RunBuilder(root=tmp_path / "archive")
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "reasoning_imagery_check", "input": {}})
    b.tool("reasoning_imagery_check", {"places": ["naip/obs:1"]}, json.dumps({"verdict": "supported"}))
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model("done")
    b.run_end()
    b.write(final_output="done")
    from core.store import FileStore

    run = Run.load(FileStore(f"file://{tmp_path}/archive"), "run-0001")
    lic = licences.for_run(run, None, judges=[], narrative_model=run.manifest.get("model_key"))
    names = [i["key"] for i in lic["items"]]
    assert not any(k.startswith("dataset unknown") for k in names) and "lgnd" in names
    models = [i for i in lic["items"] if i["role"] == "model"]
    assert len(models) == 1 and models[0]["used_as"] == "agent, narrative"
