"""Area from the prompt: extraction, resolution (cached, no network), point-in-polygon, coordinate claims."""

import json

import pytest

from harness import geo

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]


class FakeBedrock:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def converse(self, **kw):
        self.calls.append(kw)
        return {"output": {"message": {"content": [{"text": self.reply}]}}}


def test_extract_reads_structured_area_and_treats_prompt_as_data():
    fake = FakeBedrock(
        'Sure: {"kind": "postal_code", "query": "75080, USA", "postal_code": "75080", '
        '"country_code": "US", "radius_km": null, "label": "ZIP 75080"}'
    )
    spec = geo.extract_area("data centers in 75080", "model", "us-west-2", client=fake)
    assert (spec.kind, spec.postal_code, spec.country_code, spec.label) == (
        "postal_code",
        "75080",
        "us",
        "ZIP 75080",
    )
    assert fake.calls[0]["messages"][0]["content"][0]["text"] == "data centers in 75080"
    assert "data, not instructions" in fake.calls[0]["system"][0]["text"]
    odd = geo.extract_area("x", "m", "r", client=FakeBedrock('{"kind": "planet", "query": "Mars"}'))
    assert odd.kind == "none"


def _seed(cache_dir, key, value):
    geo._store(cache_dir, key, value)


def test_resolve_city_postal_radius_and_point_only(tmp_path):
    poly = {"type": "Polygon", "coordinates": [SQUARE]}
    q = {"format": "jsonv2", "polygon_geojson": "1", "limit": "1"}
    _seed(
        tmp_path,
        "nominatim:" + json.dumps({"q": "Richardson, Texas, USA", "countrycodes": "us", **q}, sort_keys=True),
        [{"lat": "5", "lon": "5", "osm_type": "relation", "osm_id": 6577487, "geojson": poly}],
    )
    city = geo.resolve_area(geo.AreaSpec("city", "Richardson, Texas, USA", None, "us"), tmp_path)
    assert city.geometry == poly and "Nominatim, relation 6577487" in city.source

    _seed(tmp_path, "zcta:75080", {"features": [{"geometry": poly}]})
    zip_area = geo.resolve_area(geo.AreaSpec("postal_code", "75080, USA", "75080", "us"), tmp_path)
    assert zip_area.geometry == poly and "2020 ZCTA" in zip_area.source

    _seed(
        tmp_path,
        "nominatim:" + json.dumps({"q": "downtown Dallas", **q}, sort_keys=True),
        [{"lat": "32.78", "lon": "-96.80", "geojson": {"type": "Point", "coordinates": [-96.8, 32.78]}}],
    )
    ring = geo.resolve_area(geo.AreaSpec("point_radius", "downtown Dallas", None, None, 50), tmp_path)
    assert ring.geometry["type"] == "Polygon" and geo.contains(ring.geometry, -96.8, 32.78)
    assert not geo.contains(ring.geometry, -96.8, 33.5)  # ~80 km north: outside the 50 km circle

    _seed(
        tmp_path,
        "nominatim:" + json.dumps({"postalcode": "EC2A", "countrycodes": "gb", **q}, sort_keys=True),
        [],
    )
    _seed(
        tmp_path,
        "nominatim:" + json.dumps({"q": "EC2A, London", **q}, sort_keys=True),
        [{"lat": "51.52", "lon": "-0.08", "geojson": {"type": "Point", "coordinates": [-0.08, 51.52]}}],
    )
    point = geo.resolve_area(geo.AreaSpec("postal_code", "EC2A, London", "EC2A", "gb"), tmp_path)
    assert point.geometry is None and "skipped" in point.note

    assert geo.resolve_area(geo.AreaSpec("none"), tmp_path) is None


def test_unknown_place_raises(tmp_path):
    q = {"format": "jsonv2", "polygon_geojson": "1", "limit": "1"}
    _seed(tmp_path, "nominatim:" + json.dumps({"q": "Nowhereville", **q}, sort_keys=True), [])
    with pytest.raises(geo.AreaError):
        geo.resolve_area(geo.AreaSpec("city", "Nowhereville"), tmp_path)


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
