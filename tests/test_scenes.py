"""Result tiles show the scene LGND matched; the mosaic is the fallback (harness/scenes.py)."""

from fastapi.testclient import TestClient

from harness import imagery, scenes, tiles
from harness.web.app import create_app
from tests.test_web import cfg_for

JPEG = b"\xff\xd8\xff" + b"0" * 64
BBOX = [73.0705, 26.5634, 73.0737, 26.5662]


class Upstream:
    def __init__(self, scene=JPEG):
        self.scene, self.calls = scene, []

    def __call__(self, url):
        self.calls.append(url)
        if url.startswith("scene://"):
            if isinstance(self.scene, Exception):
                raise self.scene
            return self.scene
        return JPEG + b"mosaic"


def test_dated_urls_and_keys_name_the_scene_and_leave_older_keys_alone():
    url = imagery.console_chip_url("s2", BBOX, "run-1", "2026-02-10")
    assert url.endswith("?run=run-1&observed=2026-02-10")
    assert "observed" not in imagery.console_chip_url("s2", BBOX, "run-1", "not a date")
    # archived mosaics keep their keys
    assert imagery.chip_key("s2", BBOX) == imagery.chip_key("s2", BBOX, None)
    assert imagery.chip_key("s2", BBOX, "2026-02-10") != imagery.chip_key("s2", BBOX)
    assert imagery.chip_key("s2", BBOX, "2026-02-10") != imagery.chip_key("s2", BBOX, "2026-03-02")
    assert scenes.label("s2", "2026-02-10").startswith("Sentinel-2 L2A scene observed 2026-02-10")
    assert scenes.label("naip", None) is None


def test_the_observed_scene_comes_first_and_a_failed_scene_falls_back_and_is_retried(tmp_path):
    up = Upstream()
    c = tiles.Cache({"out_dir": str(tmp_path)}, fetch=up)
    t = c.chip("s2", BBOX, observed="2026-02-10")
    assert t.data == JPEG and up.calls == [imagery.scene_url("s2", BBOX, "2026-02-10")]
    assert c.chip("s2", BBOX, observed="2026-02-10").origin == "cache"

    down = Upstream(scene=tiles.TileUnavailable("no scene"))
    c2 = tiles.Cache({"out_dir": str(tmp_path / "b")}, fetch=down)
    t = c2.chip("naip", BBOX, observed="2020-10-07")
    assert t.data == JPEG + b"mosaic"  # the mosaic, under its own key
    assert not c2.chip_path("naip", BBOX, "2020-10-07").exists()
    down.scene = JPEG
    assert c2.chip("naip", BBOX, observed="2020-10-07").data == JPEG  # the scene is tried again


def test_catalogue_prefers_a_scene_covering_the_chip_then_the_least_cloudy(monkeypatch):
    feats = [
        {"bbox": [73.07, 26.56, 73.072, 26.57], "properties": {"eo:cloud_cover": 0},
         "assets": {"visual": {"href": "a"}}},  # cloud-free, but doesn't cover the chip
        {"bbox": [72, 26, 74, 27], "properties": {"eo:cloud_cover": 30}, "assets": {"visual": {"href": "b"}}},
        {"bbox": [72, 26, 74, 27], "properties": {"eo:cloud_cover": 5}, "assets": {"visual": {"href": "c"}}},
    ]  # fmt: skip
    seen = {}

    def post(url, body):
        seen.update(url=url, body=body)
        return {"features": feats}

    monkeypatch.setattr(scenes, "_post_json", post)
    scenes.find.cache_clear()
    assert scenes.find("s2", tuple(BBOX), "2026-02-10") == "c"
    assert seen["body"]["collections"] == ["sentinel-2-l2a"]
    assert seen["body"]["datetime"] == "2026-02-10T00:00:00Z/2026-02-10T23:59:59Z"
    assert "earth-search" in seen["url"]


def test_tile_route_rejects_a_malformed_date(tmp_path):
    client = TestClient(create_app(cfg_for(tmp_path)))
    box = imagery.bbox_text(BBOX)
    assert client.get(f"/tiles/chip/s2/{box}.jpg?observed=yesterday").status_code == 404
