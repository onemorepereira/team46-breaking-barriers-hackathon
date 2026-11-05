"""The sharpest open image of a place: source order, footprints, fallthrough, allowlist (harness/sharp.py)."""

import io

import numpy as np
import pytest
from PIL import Image as PILImage

from harness import scenes, sharp
from harness.tiles import TileUnavailable

LAT, LON = 47.74, -117.44
BBOX = (LON - 0.001, LAT - 0.001, LON + 0.001, LAT + 0.001)
SQUARE = {"type": "Polygon", "coordinates": [[[-118, 47], [-117, 47], [-117, 48], [-118, 48], [-118, 47]]]}
ELSEWHERE = {"type": "Polygon", "coordinates": [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]}
V = "https://vantor-opendata.s3.amazonaws.com/events/"


def vantor_catalogue(item_geometry=SQUARE, href=V + "Spokane/A.tif"):
    return {
        V + "catalog.json": {
            "links": [
                {"rel": "child", "href": "./Spokane/collection.json"},
                {"rel": "child", "href": "./Far/collection.json"},
            ]
        },
        V + "Spokane/collection.json": {
            "extent": {"spatial": {"bbox": [[-118, 47, -117, 48]]}},
            "links": [{"rel": "item", "href": "./A.json"}, {"rel": "item", "href": "./B.json"}],
        },
        V + "Far/collection.json": {
            "extent": {"spatial": {"bbox": [[10, 10, 11, 11]]}},
            "links": [{"rel": "item", "href": "./Z.json"}],
        },
        V + "Spokane/A.json": {
            "bbox": [-118, 47, -117, 48],
            "geometry": item_geometry,
            "properties": {"datetime": "2026-08-03T19:02:25Z", "pan_gsd": 0.48},
            "assets": {"visual": {"href": href}},
        },
        V + "Spokane/B.json": {
            "bbox": [-118, 47, -117, 48],
            "geometry": SQUARE,
            "properties": {"datetime": "2026-08-05T19:02:25Z", "pan_gsd": 0.56},
            "assets": {"visual": {"href": V + "Spokane/B.tif"}},
        },
    }


@pytest.fixture
def net(monkeypatch):
    """Fake catalogues: URL -> JSON for GETs, a list of features per STAC endpoint for POSTs."""
    state = {"get": {}, "post": {}, "gets": []}

    def get(url):
        state["gets"].append(url)
        if url.startswith(sharp.OAM_META):
            return state["get"].get("oam", {"results": []})
        if url not in state["get"]:
            raise OSError(f"404 {url}")
        return state["get"][url]

    def post(url, body):
        v = state["post"].get(url, [])
        if isinstance(v, Exception):
            raise v
        return {"features": v}

    sharp._cache.clear()
    monkeypatch.setattr(sharp, "_get_json", get)
    monkeypatch.setattr(scenes, "_post_json", post)
    return state


def test_point_in_polygon_and_multipolygon():
    assert sharp.covers(SQUARE, LON, LAT)
    assert not sharp.covers(ELSEWHERE, LON, LAT)
    assert sharp.covers(
        {"type": "MultiPolygon", "coordinates": [ELSEWHERE["coordinates"], SQUARE["coordinates"]]}, LON, LAT
    )
    assert not sharp.covers(None, LON, LAT) and not sharp.covers({"type": "Point"}, LON, LAT)


def test_vantor_items_covering_the_point_newest_first_and_other_events_unread(net):
    net["get"].update(vantor_catalogue())
    tried = []
    imgs = list(sharp.candidates(LAT, LON, BBOX, sources=["vantor"], tried=tried))
    assert [i.href for i in imgs] == [V + "Spokane/B.tif", V + "Spokane/A.tif"]
    assert imgs[0].gsd_m == 0.56 and imgs[0].date == "2026-08-05" and imgs[0].licence == "CC BY-NC 4.0"
    assert tried == ["vantor:2"]
    assert V + "Far/Z.json" not in net["gets"]  # its extent doesn't hold the point


def test_vantor_item_footprint_must_hold_the_point_and_foreign_hosts_are_dropped(net):
    cat = vantor_catalogue(item_geometry=ELSEWHERE)
    cat[V + "Spokane/B.json"]["assets"]["visual"]["href"] = "https://evil.example/x.tif"
    net["get"].update(cat)
    assert list(sharp.candidates(LAT, LON, BBOX, sources=["vantor"])) == []


def test_oam_uses_the_item_licence_or_oam_terms_and_newest_first(net):
    net["get"]["oam"] = {
        "results": [
            {
                "uuid": "https://oin-hotosm-temp.s3.amazonaws.com/a.tif",
                "gsd": 0.05,
                "acquisition_end": "2019-01-02T00:00:00Z",
                "geojson": SQUARE,
            },
            {
                "uuid": "https://oin-hotosm-temp.s3.us-east-1.amazonaws.com/b.tif",
                "gsd": 0.1,
                "acquisition_end": "2024-05-06T00:00:00Z",
                "geojson": SQUARE,
                "license": "CC BY-NC 4.0",
                "provider": "HOT",
            },
            {
                "uuid": "https://oin-hotosm-temp.s3.amazonaws.com/c.tif",
                "gsd": 0.01,
                "acquisition_end": "2025-01-01",
                "geojson": ELSEWHERE,
            },  # bbox matched, footprint doesn't
        ]
    }
    imgs = list(sharp.candidates(LAT, LON, BBOX, sources=["oam"]))
    assert [i.href.rsplit("/", 1)[1] for i in imgs] == ["b.tif", "a.tif"]
    assert imgs[0].licence == "CC BY-NC 4.0" and imgs[0].credit == "OpenAerialMap (HOT)"
    assert imgs[1].licence == "CC BY 4.0" and imgs[1].date == "2019-01-02"


def test_source_order_and_a_failing_catalogue_is_skipped(net):
    net["post"][sharp.NAIP_SEARCH] = RuntimeError("pc down")
    net["post"][sharp.S2_SEARCH] = [
        {
            "properties": {"datetime": "2026-10-01T00:00:00Z"},
            "assets": {"visual": {"href": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/x.tif"}},
        }
    ]
    tried = []
    imgs = list(sharp.candidates(LAT, LON, BBOX, tried=tried))
    assert [i.source for i in imgs] == ["s2"] and imgs[0].gsd_m == 10.0 and imgs[0].date == "2026-10-01"
    assert tried == ["vantor:error OSError", "oam:none", "naip:error RuntimeError", "s2:1"]


def test_s2_prefers_the_observed_scene_of_an_s2_chip(net, monkeypatch):
    monkeypatch.setattr(
        scenes, "find", lambda index, bbox, observed: "https://sentinel-cogs.s3.us-west-2.amazonaws.com/o.tif"
    )
    imgs = list(sharp.candidates(LAT, LON, BBOX, observed="2026-04-11", index="s2", sources=["s2"]))
    assert imgs[0].href.endswith("o.tif") and imgs[0].date == "2026-04-11"


def test_allowlist_is_exact_and_https_only():
    assert sharp.allowed("https://vantor-opendata.s3.amazonaws.com/events/x.tif")
    for bad in (
        "http://vantor-opendata.s3.amazonaws.com/x.tif",
        "s3://vantor-opendata/x.tif",
        "./x.tif",
        "https://vantor-opendata.s3.amazonaws.com.evil.example/x.tif",
        "https://oin-hotosm-other.s3.amazonaws.com/x",
    ):
        assert not sharp.allowed(bad), bad
    with pytest.raises(TileUnavailable):
        sharp.read(sharp.Image("oam", "https://evil.example/x.tif", 1, None, "", ""), BBOX)


def _tif(tmp_path, filled_cols):
    """A small EPSG:4326 GeoTIFF over BBOX whose left `filled_cols` of 10 columns hold data."""
    import rasterio
    from rasterio.transform import from_bounds

    data = np.zeros((3, 10, 10), dtype="uint8")
    data[:, :, :filled_cols] = 120
    path = tmp_path / "t.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=3,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_bounds(*BBOX, 10, 10),
    ) as dst:
        dst.write(data)
    return str(path)


def test_render_min_coverage_rejects_a_mostly_empty_window(tmp_path):
    full = scenes.render(_tif(tmp_path, 10), BBOX, size=32, min_coverage=0.9)
    assert PILImage.open(io.BytesIO(full)).size == (32, 32)
    part = _tif(tmp_path, 3)
    assert scenes.render(part, BBOX, size=32)  # default: any data is enough, as before
    with pytest.raises(TileUnavailable, match="only part"):
        scenes.render(part, BBOX, size=32, min_coverage=0.9)


def test_only_geotiff_is_opened_so_a_vrt_named_tif_cannot_reach_other_files(tmp_path):
    inner = _tif(tmp_path, 10)
    vrt = tmp_path / "evil.tif"
    vrt.write_text(
        '<VRTDataset rasterXSize="10" rasterYSize="10"><VRTRasterBand dataType="Byte" band="1">'
        f"<SimpleSource><SourceFilename>{inner}</SourceFilename><SourceBand>1</SourceBand></SimpleSource>"
        "</VRTRasterBand></VRTDataset>"
    )
    with pytest.raises(Exception) as e:
        scenes.render(str(vrt), BBOX, size=32)
    assert "not recognized" in str(e.value) or "GTiff" in str(e.value) or "TIFF" in str(e.value)


def test_ports_other_than_443_are_refused():
    assert sharp.allowed("https://vantor-opendata.s3.amazonaws.com:443/x.tif")
    assert not sharp.allowed("https://vantor-opendata.s3.amazonaws.com:8443/x.tif")
    assert not sharp.allowed("https://vantor-opendata.s3.amazonaws.com:notaport/x.tif")


def test_a_failed_scene_read_never_returns_the_signed_url(monkeypatch):
    monkeypatch.setattr(
        scenes, "find", lambda index, bbox, observed: "https://naipeuwest.blob.core.windows.net/a.tif"
    )
    monkeypatch.setattr(scenes, "_signed", lambda index, href: f"{href}?sig=SECRET")

    def boom(href, bbox, size=384, min_coverage=0.0):
        raise RuntimeError(f"'/vsicurl/{href}' not recognized")

    monkeypatch.setattr(scenes, "render", boom)
    with pytest.raises(TileUnavailable) as e:
        scenes.scene_jpeg("naip", list(BBOX), "2022-07-04")
    assert "SECRET" not in str(e.value) and "a.tif?…" in str(e.value)
