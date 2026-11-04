"""LGND result parsing (chips, verdicts, tables) and the trouble-spot rule for unscoped searches."""

import json

from harness.web.live import span_event
from tools.lgnd.results import extras


def test_lgnd_search_and_check_parsing():
    search = {
        "matches": {
            "columns": ["node", "chip_id", "place", "observed", "lat", "lon", "bbox", "similarity"],
            "rows": [
                ["naip/obs:1", "chip_a", "p", "2020-10-14", 32.9, -96.7, [-96.71, 32.96, -96.70, 32.97], 0.3]
            ],
        }
    }  # noqa: E501
    chips = extras(json.dumps(search))["chips"]
    assert chips[0]["node"] == "naip/obs:1" and chips[0]["bbox"] == [-96.71, 32.96, -96.70, 32.97]
    check = {
        "verdict": "partly supported",
        "places": {
            "columns": ["node", "answer", "reason"],
            "rows": [["naip/obs:1", "yes", "rooftop cooling"]],
        },
    }
    ex = extras(json.dumps(check))
    assert ex["verdict"] == "partly supported" and ex["verdicts"][0]["answer"] == "yes"
    assert extras("not json") == {}


def test_non_decision_spans_are_ignored():
    assert span_event({"name": "chat", "attributes": {}}) is None


def test_unscoped_search_is_flagged(tmp_path):
    from analysis.provenance import grade
    from analysis.summary import build
    from analysis.trace import Run
    from core.store import FileStore
    from tests.fixtures.builder import RunBuilder

    b = RunBuilder(root=tmp_path)
    b.run_start()
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "search_place_find", "input": {}})
    sid, _ = b.tool(
        "search_place_find", {"scope": {"index": "naip"}}, json.dumps({"where": "everywhere", "matches": {}})
    )
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model("done")
    b.run_end()
    b.write(final_output="done")
    run = Run.load(FileStore(f"file://{tmp_path}"), "run-0001")
    assert any("searched everywhere" in t.reason for t in build(run, grade(run)).trouble_spots)
    assert extras(json.dumps({"where": "everywhere", "matches": {}}))["unscoped"] is True


def test_lgnd_classifier_and_cell_tables_become_chips():
    classifier = {
        "targets": "polygon with 407 vertices",
        "results": {
            "columns": ["node", "period", "lat", "lon", "bbox", "label", "margin", "fit"],
            "rows": [
                [
                    "s2/f1.2021@all",
                    "all",
                    18.52,
                    102.66,
                    [102.62, 18.47, 102.71, 18.57],
                    "farmland",
                    0.2,
                    "close",
                ]
            ],
        },
    }
    c = extras(json.dumps(classifier))["chips"][0]
    assert c["index"] == "s2" and c["label"] == "farmland" and c["bbox"] == [102.62, 18.47, 102.71, 18.57]
    cells = {
        "area": "polygon with 407 vertices",
        "cell_km": 123,
        "cells": {"columns": ["node", "lat", "lon"], "rows": [["s2/f1.202102@all", 18.37, 102.81]]},
    }
    b = extras(json.dumps(cells))["chips"][0]["bbox"]
    assert b[0] < 102.81 < b[2] and b[1] < 18.37 < b[3] and round(b[3] - b[1], 2) == round(123 / 111.32, 2)


def test_tile_source_by_index():
    from harness.imagery import tile_url

    assert "nationalmap.gov" in tile_url("naip", [-96.7, 32.9, -96.6, 33.0])
    assert "maps.eox.at" in tile_url("s2", [102.6, 18.4, 102.7, 18.5]) and "s2cloudless" in tile_url(
        "s2", [0, 0, 1, 1]
    )


def test_single_place_result_becomes_a_chip():
    one = {
        "node": "s2/obs:1",
        "observed": "2026-04-10",
        "lat": 18.0,
        "lon": 102.6,
        "bbox": [102.59, 17.99, 102.6, 18.0],
    }
    chip = extras(json.dumps(one))["chips"][0]
    assert chip["node"] == "s2/obs:1" and chip["index"] == "s2" and chip["bbox"] == one["bbox"]
