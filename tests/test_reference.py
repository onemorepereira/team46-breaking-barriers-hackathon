"""Reference sets and the benchmark's matching rule (docs/adb-alignment/spec.md AC1-AC3)."""

import json

import pytest

from analysis import reference as R

# A 1 km x 1 km square near the equator, so 160 m cells are easy to reason about.
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0.009, 0], [0.009, 0.009], [0, 0.009], [0, 0]]]}


def meta(**over):
    m = {"schema_version": 1, "id": "t", "concept": "solar_farm", "place": "Testville", "area": SQUARE,
         "completeness": "complete", "completeness_note": "all of them", "source": {"name": "test"},
         "licence": {"id": "CC-BY-4.0", "name": "CC BY 4.0", "url": "https://x", "commercial_use_ok": True},
         "unit": "asset", "cell_m": 160}  # fmt: skip
    m.update(over)
    return m


def point(lon, lat, rid):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"ref_id": rid},
    }


def make(features, **over):
    fc = {"type": "FeatureCollection", "features": features}
    raw = json.dumps(fc).encode()
    return R.parse(meta(**over), fc, raw)


def test_loader_refuses_missing_or_non_commercial_licences():
    with pytest.raises(R.ReferenceError, match="licence"):
        make([point(0.001, 0.001, "a")], licence={})
    with pytest.raises(R.ReferenceError, match="commercial_use_ok"):
        make(
            [point(0.001, 0.001, "a")],
            licence={"id": "x", "name": "x", "url": "u", "commercial_use_ok": False},
        )
    nc = {"id": "CC-BY-NC-4.0", "name": "CC BY-NC", "url": "u", "commercial_use_ok": True}
    with pytest.raises(R.ReferenceError, match="non-commercial"):
        make([point(0.001, 0.001, "a")], licence=nc)
    with pytest.raises(R.ReferenceError, match="completeness"):
        make([point(0.001, 0.001, "a")], completeness="mostly")
    with pytest.raises(R.ReferenceError, match="no features"):
        make([])


def test_any_touch_matching_recall_precision_count_ratio_and_lift():
    g = R.Grid.for_area(SQUARE, 160)
    # three point assets; the agent claims one exactly, one in the same cell, and one far from any asset
    a, b, c = point(0.0005, 0.0005, "a"), point(0.004, 0.004, "b"), point(0.008, 0.008, "c")
    ref = make([a, b, c])
    same_cell_as_b = (0.0041, 0.0041)
    assert g.cell(*same_cell_as_b) == g.cell(0.004, 0.004)
    claims = [
        (0.0005, 0.0005),
        (same_cell_as_b[1], same_cell_as_b[0]),
        (0.0065, 0.0005),
        (5.0, 5.0),
    ]  # (lat, lon)
    out = R.score(ref, claims)
    assert out["found"] == ["a", "b"] and out["missed"] == ["c"]
    assert out["site_recall"] == round(2 / 3, 3)
    assert out["cell_precision"] == round(2 / 3, 3)  # 3 flagged cells, 2 touch an asset
    assert out["count_ratio"] == 1.0  # 3 separate sites / 3 assets
    assert out["outside_area"] == 1 and out["claims_scored"] == 3
    assert out["lift"] and out["lift"] > 1 and len(out["false_alarm_cells"]) == 1


def test_a_polygon_asset_is_found_by_any_flagged_cell_it_touches_and_counts_once():
    big = {"type": "Feature", "properties": {"ref_id": "farm"},
           "geometry": {"type": "Polygon", "coordinates": [[[0.001, 0.001], [0.006, 0.001], [0.006, 0.006],
                                                             [0.001, 0.006], [0.001, 0.001]]]}}  # fmt: skip
    ref = make([big])
    corner_of_farm = (0.00105, 0.00105)  # (lat, lon), inside the farm's south-west cell
    out = R.score(ref, [corner_of_farm, (0.0058, 0.0058)])
    assert out["found"] == ["farm"] and out["site_recall"] == 1.0
    assert out["cell_precision"] == 1.0
    g = R.Grid.for_area(SQUARE, 160)
    assert len(R.asset_cells(g, big["geometry"])) > 9  # spans many cells, still one asset


def test_neighbouring_flagged_cells_merge_into_one_site():
    ref = make([point(0.0005, 0.0005, "a")])
    # two claims in adjacent cells -> one site; count ratio 1.0
    out = R.score(ref, [(0.0005, 0.0005), (0.0005, 0.0019)])
    assert out["sites"] == 1 and out["count_ratio"] == 1.0


def test_incomplete_reference_reports_precision_only():
    ref = make([point(0.0005, 0.0005, "a")], completeness="incomplete")
    out = R.score(ref, [(0.0005, 0.0005)])
    assert out["site_recall"] is None and out["count_ratio"] is None and out["lift"] is None
    assert out["cell_precision"] == 1.0 and "incomplete" in out["notes"][0]


def test_no_claims_means_recall_zero_and_precision_undefined():
    out = R.score(make([point(0.0005, 0.0005, "a")]), [])
    assert out["site_recall"] == 0.0 and out["cell_precision"] is None
    assert out["notes"] == ["no located sites inside the reference area to check"]


def test_sha_changes_with_the_features():
    a = make([point(0.0005, 0.0005, "a")]).sha256
    b = make([point(0.0006, 0.0005, "a")]).sha256
    assert a != b
