"""City-limits check: parsing, point-in-polygon (with holes and multipolygons), coordinate claims."""

import json

import pytest

from harness import geo

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]


def test_parse_city():
    assert geo.parse_city("Richardson, TX") == ("Richardson", "TX")
    assert geo.parse_city(" san antonio , tx ") == ("san antonio", "TX")
    with pytest.raises(geo.BoundaryError):
        geo.parse_city("Richardson Texas")


def test_point_in_polygon_with_hole_and_multipolygon():
    poly = {"type": "Polygon", "coordinates": [SQUARE, HOLE]}
    assert geo.contains(poly, 1, 1) and not geo.contains(poly, 5, 5) and not geo.contains(poly, 11, 5)
    multi = {
        "type": "MultiPolygon",
        "coordinates": [[SQUARE], [[[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]]],
    }
    assert geo.contains(multi, 25, 25) and not geo.contains(multi, 15, 15)


def test_coordinate_claims():
    assert geo.coordinate_pair("32.965, -96.7121") == (32.965, -96.7121)
    assert geo.coordinate_pair("naip/obs:1") is None and geo.coordinate_pair("200, 10") is None


def test_cached_boundary_is_used_without_network(tmp_path):
    cache = tmp_path / "TX-richardson.geojson"
    feature = {
        "type": "Feature",
        "properties": {"GEOID": "4861796"},
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    }
    cache.write_text(json.dumps(feature))
    assert geo.fetch_boundary("Richardson", "TX", tmp_path)["properties"]["GEOID"] == "4861796"
