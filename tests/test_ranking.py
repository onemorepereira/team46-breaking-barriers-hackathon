"""Ranking metrics: recall@k, AUROC, AP, review effort (docs/ranking-metrics, analysis/reference.py)."""

import pytest

from analysis import reference as R
from tests.test_reference import SQUARE, make, point

# AC5 fixture: a 10 x 10-cell area with 3 single-cell assets.
CELLS = [(i, j) for i in range(10) for j in range(10)]
A, B, C = (1, 1), (5, 5), (8, 2)
POS = {A, B, C}
ASSETS = {A: {"a"}, B: {"b"}, C: {"c"}}


def metrics(ranked, complete=True):
    return R.ranking_metrics(ranked, ASSETS, 3, POS, 100, complete)


def negatives(n):
    return [c for c in CELLS if c not in POS][:n]


def test_known_answers_perfect_ranking():
    m = metrics([A, B, C, *negatives(5)])
    assert m["auroc"] == 1.0 and m["ap"] == 1.0
    assert m["effort"]["80"] == {"cells": 3} and m["effort"]["50"] == {"cells": 2}
    assert m["k"] == 3 and m["recall_at_k"] == 1.0
    assert m["random_effort"] == {"50": 50, "80": 80, "90": 90}


def test_known_answers_ap_half_at_ranks_2_4_6():
    n = negatives(3)
    m = metrics([n[0], A, n[1], B, n[2], C])
    assert m["ap"] == 0.5  # (1/2 + 2/4 + 3/6) / 3
    assert m["recall_at_k"] == pytest.approx(1 / 3, abs=1e-3)  # top 3 holds one asset


def test_empty_ranking():
    m = metrics([])
    assert m["auroc"] == 0.5 and m["ap"] == 0.0
    assert m["effort"]["80"] == {"cells": None, "reached": 0.0, "after": 0}
    assert "no ranked candidates inside the reference area" in m["notes"]


def test_auroc_counts_the_unranked_block_as_a_half_tie():
    # one positive ranked first; two positives unranked; 97 negatives all unranked
    m = metrics([A])
    # wins: A beats all 97 negatives; unranked pairs: 2 positives x 97 negatives at 1/2
    assert m["auroc"] == pytest.approx((97 + 0.5 * 2 * 97) / (3 * 97), abs=1e-3)


def test_recall_at_fixed_k_and_effort_not_reached():
    m = metrics([A, *negatives(30), B])
    assert m["recall_at"]["10"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["recall_at"]["50"] == pytest.approx(2 / 3, abs=1e-3)  # list shorter than 50: all of it counts
    assert m["effort"]["50"] == {"cells": 32}
    assert m["effort"]["80"] == {"cells": None, "reached": 0.667, "after": 32}


def test_incomplete_reference_keeps_auroc_and_ap_only():
    m = metrics([A, B], complete=False)
    assert m["recall_at_k"] is None and m["effort"] is None and m["recall_at"] is None
    assert m["auroc"] is not None and m["ap"] == pytest.approx(2 / 3, abs=1e-3)
    assert any("negatives may include unrecorded assets" in n for n in m["notes"])


def test_no_assets_in_the_area():
    m = R.ranking_metrics([A], {}, 0, set(), 100, True)
    assert m["auroc"] is None and m["ap"] is None and m["recall_at_k"] is None
    assert "no reference assets inside the area" in m["notes"]


def test_order_claims_then_each_calls_results_interleaved_dedup_area_only():
    g = R.Grid.for_area(SQUARE, 160)
    claims = [(0.0072, 0.0072)]
    chips = [
        (0.0005, 0.0005, 0.2, "T1"),  # T1's second best
        (0.0040, 0.0040, 0.9, "T1"),  # T1's best
        (0.0072, 0.0072, 0.99, "T2"),  # T2's best, but the claim's cell: already ranked
        (0.0030, 0.0060, 0.1, "T2"),  # T2's second
        (0.0500, 0.0500, 0.95, "T1"),  # outside the area: skipped
    ]
    ranked = R.rank_cells(g, SQUARE, claims, chips)
    # T1 by similarity: .95 (outside, skipped), .9, .2; T2: .99 (the claim's cell, a duplicate), .1
    # round-robin: claim, T1[.95 skip], T2[.99 dup], T1[.9], T2[.1], T1[.2]
    assert ranked == [
        g.cell(0.0072, 0.0072),
        g.cell(0.0040, 0.0040),
        g.cell(0.0060, 0.0030),
        g.cell(0.0005, 0.0005),
    ]


def test_similarities_from_different_calls_are_not_compared():
    g = R.Grid.for_area(SQUARE, 160)
    # T1 scores are all higher than T2's, yet T2's best ranks second (round-robin), not after all of T1
    chips = [(0.0010, 0.0010, 0.9, "T1"), (0.0020, 0.0020, 0.8, "T1"), (0.0060, 0.0060, 0.3, "T2")]
    assert R.rank_cells(g, SQUARE, [], chips) == [
        g.cell(0.0010, 0.0010),
        g.cell(0.0060, 0.0060),
        g.cell(0.0020, 0.0020),
    ]


def test_equal_similarities_keep_first_seen_order():
    g = R.Grid.for_area(SQUARE, 160)
    chips = [(0.0010, 0.0010, 0.5, "T1"), (0.0050, 0.0050, 0.5, "T1")]
    assert R.rank_cells(g, SQUARE, [], chips) == [g.cell(0.0010, 0.0010), g.cell(0.0050, 0.0050)]


def test_score_carries_the_ranking_only_when_chips_are_given():
    ref = make([point(0.0011, 0.0011, "a"), point(0.0071, 0.0071, "b")])
    base = R.score(ref, [(0.0011, 0.0011)])
    assert "ranking" not in base
    out = R.score(ref, [(0.0011, 0.0011)], [(0.0071, 0.0071, 0.8, "T1"), (0.0040, 0.0040, 0.5, "T1")])
    rk = out["ranking"]
    assert out["site_recall"] == 0.5  # the claim-only metrics are unchanged
    assert rk["candidates"] == 3 and rk["positives"] == 2 and rk["recall_at_k"] == 1.0
    assert rk["effort"]["80"] == {"cells": 2} and rk["ap"] == 1.0


def test_compare_rows_and_concepts_carry_the_ranking():
    from analysis.report import _ranking_cols, concept_rows

    cols = _ranking_cols({"recall_at_k": 0.5, "auroc": 0.8, "ap": 0.3, "effort": {"80": {"cells": 12}}})
    assert cols == {"recall_at_k": 0.5, "auroc": 0.8, "ap": 0.3, "effort_80": 12}
    assert _ranking_cols({"effort": {"80": {"cells": None, "reached": 0.4, "after": 9}}})["effort_80"] is None
    rows = [
        {
            "concept": "solar_farm",
            "score": 90,
            "site_recall": 0.5,
            "cell_precision": 1,
            "count_ratio": 0.5,
            "recall_at_k": 0.5,
            "auroc": 0.8,
            "ap": 0.4,
            "effort_80": 10,
        },
        {
            "concept": "solar_farm",
            "score": 80,
            "site_recall": None,
            "cell_precision": None,
            "count_ratio": None,
            "recall_at_k": None,
            "auroc": 0.6,
            "ap": 0.2,
            "effort_80": None,
        },
    ]
    c = concept_rows(rows)[0]
    assert (c["recall_at_k"], c["auroc"], c["ap"], c["effort_80"]) == (0.5, 0.7, 0.3, 10.0)


# ---------- wiring: per-call candidates, report and API ----------
def two_call_run(root):
    """Two LGND search calls that both return (0.008, 0.008), plus a classifier row with no similarity."""
    import json

    from analysis.trace import Run
    from core.store import FileStore
    from tests.fixtures.builder import RunBuilder
    from tests.test_adb_alignment import SQUARE as AREA

    def matches(rows):
        box = lambda lat, lon: [lon - 0.0005, lat - 0.0005, lon + 0.0005, lat + 0.0005]  # noqa: E731
        rows = [[n, lat, lon, box(lat, lon), sim] for n, lat, lon, sim in rows]
        return json.dumps(
            {"matches": {"columns": ["node", "lat", "lon", "bbox", "similarity"], "rows": rows}}
        )

    answer = (
        "Found.\n```json\n"
        + json.dumps({"claims": [{"claim": "site", "value": "0.0005, 0.0005", "ref": "T1"}]})
        + "\n```"
    )
    b = RunBuilder(root=root, run_id="run-0001")
    b.run_start()
    for ref, rows in (
        ("T1", [["s2/obs:9", 0.004, 0.004, 0.9], ["s2/obs:8", 0.008, 0.008, 0.2]]),
        ("T2", [["s2/obs:8", 0.008, 0.008, 0.95]]),  # T2's best: already returned by T1, lower down
    ):
        b.model("", tool_use={"toolUseId": f"tooluse_{ref}", "name": "search_place_find", "input": {}})
        b.tool("search_place_find", {"scope": {"index": "s2"}}, matches(rows), ref=ref)
        b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model("", tool_use={"toolUseId": "tooluse_T3", "name": "toolbox_classifier_apply", "input": {}})
    b.tool(
        "toolbox_classifier_apply",
        {},
        json.dumps(
            {
                "results": [
                    {"lat": 0.006, "lon": 0.006, "bbox": [0.0055, 0.0055, 0.0065, 0.0065], "label": "no"}
                ]
            }
        ),
        ref="T3",
    )
    b.lines[-1]["attributes"]["harness.tool.server"] = "lgnd"
    b.model(answer)
    b.run_end()
    b.write(
        final_output=answer,
        search_area={
            "label": "Testville",
            "source": "OpenStreetMap Nominatim, relation 1",
            "geometry": AREA,
            "mode": "enforce",
        },
    )
    return Run.load(FileStore(f"file://{root}"), "run-0001")


def test_search_candidates_are_per_call_and_skip_unscored_rows(tmp_path):
    from analysis.judging import measure

    run = two_call_run(tmp_path)
    cands = measure.search_candidates(run)
    assert cands == [(0.004, 0.004, 0.9, "T1"), (0.008, 0.008, 0.2, "T1"), (0.008, 0.008, 0.95, "T2")]
    # located_results keeps the place once, under T1; the ranking sees T2's own best result at depth 1
    located = [x for x in measure.measure(run).located if x.source == "chip" and x.similarity is not None]
    assert [(x.lat, x.ref) for x in located if x.lat == 0.008] == [(0.008, "T1")]  # located keeps it once


def test_the_report_and_api_carry_the_ranking(tmp_path):
    from analysis import report
    from analysis.trace import Run
    from harness import reference as H
    from harness.web.view import run_view
    from tests.test_adb_alignment import write_set

    refs = tmp_path / "refs"
    write_set(refs)  # assets at (0.0005, 0.0005) and (0.008, 0.008)
    run = two_call_run(tmp_path / "archive")
    H.tie(run.store, run.run_id, "t-set", by="cli", root=refs)
    run = Run.load(run.store, run.run_id)
    rk = report.analyze(run).reference["ranking"]
    # claim cell (asset a), then depth 1: T1 best (0.004, empty), T2 best (asset b): both assets by rank 3
    # k = 2 positive cells: the top 2 (claim, T1's empty best) hold one asset; T2's best adds b at rank 3
    assert rk["candidates"] == 3 and rk["k"] == 2 and rk["recall_at_k"] == 0.5
    assert rk["effort"]["80"] == {"cells": 3} and rk["recall_at"]["10"] == 1.0
    assert run_view(run)["reference"]["ranking"]["candidates"] == 3


def test_calls_are_interleaved_in_the_order_they_were_made_not_completed():
    g = R.Grid.for_area(SQUARE, 160)
    # T2's result arrived before T1's (parallel calls), but T1 was made first
    chips = [(0.0060, 0.0060, 0.9, "T2"), (0.0010, 0.0010, 0.9, "T1"), (0.0030, 0.0030, 0.9, "T?")]
    assert R.rank_cells(g, SQUARE, [], chips) == [
        g.cell(0.0010, 0.0010),
        g.cell(0.0060, 0.0060),
        g.cell(0.0030, 0.0030),
    ]
