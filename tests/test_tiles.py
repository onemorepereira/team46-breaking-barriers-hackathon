"""docs/tile-cache: the disk cache, its lookup order and failure behaviour, and archiving result tiles.
No network: the upstream fetch is faked; freshness uses an injected clock and explicit mtimes; no sleeps."""

import os
import time

import pytest

from core.store import FileStore
from harness import imagery, tiles

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-tile"
PNG = b"\x89PNG\r\n" + b"png-tile"
BBOX = [-96.75, 32.95, -96.74, 32.96]
NOW = time.time()  # captured once; files the cache writes get real mtimes near it


class FakeUpstream:
    def __init__(self, reply=JPEG):
        self.reply, self.calls = reply, []

    def __call__(self, url):
        self.calls.append(url)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def cache(tmp_path, reply=JPEG, **settings):
    cfg = {"out_dir": str(tmp_path / "out"), "tiles": settings}
    up = FakeUpstream(reply)
    return tiles.Cache(cfg, fetch=up, now=lambda: NOW), up


def test_upstream_then_disk_then_stale_and_never_an_error_page(tmp_path):
    c, up = cache(tmp_path)
    first = c.base("s2", 3, 1, 2)
    assert first.origin == "upstream" and first.content_type == "image/jpeg"
    assert up.calls == ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g/3/2/1.jpg"]
    path = c.base_path("s2", 3, 1, 2)
    os.utime(path, (NOW - 60, NOW - 60))
    assert c.base("s2", 3, 1, 2).origin == "cache" and len(up.calls) == 1  # warm: no upstream call

    os.utime(path, (NOW - 31 * 86400, NOW - 31 * 86400))  # older than max_age_days (30)
    up.reply = OSError("provider down")
    assert c.base("s2", 3, 1, 2).origin == "stale"
    up.reply = b"<ServiceExceptionReport>bad bbox</ServiceExceptionReport>"  # HTTP 200, not an image
    assert c.base("s2", 3, 1, 2).origin == "stale"

    bad, _ = cache(tmp_path / "other", reply=b'{"error": {"code": 400}}')
    with pytest.raises(tiles.TileUnavailable):
        bad.base("usgs", 1, 0, 0)
    assert not list((tmp_path / "other" / "out").rglob("*.jpg"))  # the error page was never cached


def test_chip_prefers_the_archive_over_the_provider_and_sniffs_png(tmp_path):
    store = FileStore(f"file://{tmp_path}/archive")
    key = tiles.archive_key("r1", "naip", BBOX)
    store.write_bytes(key, PNG)
    c, up = cache(tmp_path, reply=OSError("offline"))
    t = c.chip("naip", BBOX, archive=(store, key))
    assert t.origin == "archive" and t.content_type == "image/png" and up.calls == []
    assert c.chip("naip", BBOX).origin == "cache"  # copied to disk on the way through


def test_eviction_drops_least_recently_used_tiles_under_the_cap(tmp_path):
    c, _ = cache(tmp_path, cache_max_mb=0.001)  # ~1 KB cap
    for i in range(6):
        p = c.base_path("usgs", 5, i, 0)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(JPEG + b"x" * 300)
        os.utime(p, (NOW - 1000 + i, NOW - 1000 + i))  # tile 0 is the least recently used
    assert c.evict() > 0
    left = sorted(int(p.parent.name) for p in (c.root / "base" / "usgs" / "5").rglob("*.jpg"))
    assert left and left == list(range(6 - len(left), 6))  # the oldest went first


def test_inputs_are_validated_before_any_url_is_built():
    assert imagery.valid_xyz("naip", 19, 0, 0) and not imagery.valid_xyz("naip", 20, 0, 0)
    assert not imagery.valid_xyz("s2", 2, 4, 0) and not imagery.valid_xyz("osm", 1, 0, 0)
    assert not imagery.valid_xyz("https://evil.example", 1, 0, 0)
    for bad in ["1,2,3", "nan,0,0.1,0.1", "0,0,2.5,1", "10,0,9,0.1", "0,-90,0.1,-89.9", "a,b,c,d"]:
        assert imagery.parse_bbox(bad) is None, bad
    assert imagery.parse_bbox("-96.75,32.95,-96.74,32.96") == BBOX
    # NAIP's Web Mercator tile bbox: z0 is the whole world
    assert "bbox=-20037508.342789244%2C-20037508.342789244%2C20037508.342789244%2C20037508.342789244" in (
        imagery.base_url("naip", 0, 0, 0)
    )
    assert imagery.console_chip_url(None, BBOX, "r1").startswith("/tiles/chip/s2/")  # unknown index -> s2


def test_archive_run_tiles_copies_each_result_tile_once(tmp_path):
    from tests.test_judging import lgnd_run

    run = lgnd_run(tmp_path / "archive")
    c, up = cache(tmp_path)
    first = tiles.archive_run_tiles({"out_dir": str(tmp_path / "out")}, run, cache=c)
    n = len(tiles.run_chips(run))
    assert n > 0 and first == {"fetched": n, "present": 0, "failed": 0}
    again = tiles.archive_run_tiles({"out_dir": str(tmp_path / "out")}, run, cache=c)
    assert again == {"fetched": 0, "present": n, "failed": 0} and len(up.calls) == n  # nothing fetched twice

    # Replay without the providers: a fresh machine (empty disk cache) serves every tile from the archive.
    fresh, dead = cache(tmp_path / "second-machine", reply=OSError("offline"))
    for index, bbox in tiles.run_chips(run):
        key = tiles.archive_key(run.run_id, index, bbox)
        assert fresh.chip(index, bbox, archive=(run.store, key)).origin == "archive"
    assert dead.calls == []


def test_fetch_upstream_sends_user_agent_and_timeout(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return JPEG

    def fake_urlopen(req, timeout):
        seen.update(ua=req.get_header("User-agent"), timeout=timeout, url=req.full_url)
        return Resp()

    monkeypatch.setattr(tiles.urllib.request, "urlopen", fake_urlopen)
    assert tiles.fetch_upstream("https://tiles.maps.eox.at/x.jpg") == JPEG
    assert seen["ua"].startswith("TeamFoundryConsole/1 (+https://")
    assert seen["timeout"] == tiles.TIMEOUT_S == 30  # USGS NAIP cold requests took ~13 s
    with pytest.raises(tiles.TileUnavailable):
        tiles.fetch_upstream("file:///etc/passwd")  # only https provider URLs


def test_archive_bounds_cap_deadline_and_stale_not_archived(tmp_path, monkeypatch):
    import threading

    from tests.test_judging import lgnd_run

    run = lgnd_run(tmp_path / "archive")
    n = len(tiles.run_chips(run))
    monkeypatch.setattr(tiles, "MAX_RUN_TILES", 1)
    assert len(tiles.run_chips(run)) == 1  # the cap
    monkeypatch.setattr(tiles, "MAX_RUN_TILES", 120)

    gate = threading.Event()  # fetches block until the archiver has returned at its deadline

    def gated(url):
        gate.wait(5)
        return JPEG

    monkeypatch.setattr(tiles, "RUN_DEADLINE_S", 0.05)
    slow = tiles.Cache({"out_dir": str(tmp_path / "out")}, fetch=gated, now=lambda: NOW)
    counts = tiles.archive_run_tiles({}, run, cache=slow)
    gate.set()
    assert counts["fetched"] == 0 and counts.get("skipped", 0) + counts["failed"] == n

    c, up = cache(tmp_path / "stale")  # only an expired copy, and the provider down: not archived
    for index, bbox in tiles.run_chips(run):
        p = c.chip_path(index, bbox)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(JPEG)
        os.utime(p, (NOW - 40 * 86400, NOW - 40 * 86400))
    up.reply = OSError("down")
    monkeypatch.setattr(tiles, "RUN_DEADLINE_S", 45)
    fresh_run = lgnd_run(tmp_path / "archive2")
    counts = tiles.archive_run_tiles({}, fresh_run, cache=c)
    assert counts["fetched"] == 0 and counts["failed"] == n
    assert not list((tmp_path / "archive2").rglob("tiles/**/*.jpg"))


def test_archive_breaker_skips_the_archive_after_an_error():
    clock = [100.0]
    no_index = type("NoIndex", (), {"run_uri": lambda self, run_id: None})()
    a = tiles.Archives({"archive_uri": "file:///tmp/none"}, index=no_index, now=lambda: clock[0])
    assert a.store_for("run-1") is not None
    a.failed()
    assert a.store_for("run-1") is None  # open for 60 s
    clock[0] += 61
    assert a.store_for("run-1") is not None


def test_write_report_survives_tile_failures(tmp_path, monkeypatch):
    from harness.cli import write_report
    from tests.test_judging import lgnd_run

    run = lgnd_run(tmp_path / "archive")

    def boom(cfg, run):
        raise RuntimeError("S3 unreachable")

    monkeypatch.setattr(tiles, "archive_run_tiles", boom)
    cfg = {"out_dir": str(tmp_path / "out"), "tiles": {"archive": True}}
    assert write_report(cfg, run).is_file()  # the report stands


def test_console_archives_after_done(tmp_path, monkeypatch):
    """live.rejudge sets `done` with the full view while tile archiving is still blocked in the background."""
    import threading

    from harness.manifest import Index
    from harness.web import live
    from tests.test_judging import lgnd_run

    run = lgnd_run(tmp_path / "archive")
    cfg = {"out_dir": str(tmp_path / "out"), "archive_uri": f"file://{tmp_path}/archive",
           "tiles": {"archive": True}}  # fmt: skip
    gate, started = threading.Event(), threading.Event()

    def blocked(cfg, run):
        started.set()
        gate.wait(5)

    monkeypatch.setattr(live, "judge_into", lambda *a: None)
    monkeypatch.setattr("harness.cli.archive_tiles_quietly", blocked)
    state = live.rejudge(cfg, Index(cfg["out_dir"]), run.run_id)
    assert started.wait(5)  # archiving began...
    assert state.done and state.final["type"] == "done" and "view" in state.final  # ...after done was set
    gate.set()


def test_wide_boxes_keep_the_provider_url_and_a_vanished_file_doesnt_stop_eviction(tmp_path, monkeypatch):
    wide = [0.0, 0.0, 3.0, 1.0]  # wider than the endpoint serves
    assert imagery.console_chip_url("s2", wide, "r1").startswith("https://tiles.maps.eox.at/")
    c, _ = cache(tmp_path, cache_max_mb=0.0005)
    for i in range(4):
        p = c.base_path("usgs", 4, i, 0)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(JPEG + b"x" * 300)
    real_stat, gone = os.stat, c.base_path("usgs", 4, 0, 0)

    def flaky_stat(path, *a, **k):  # one file disappears between the walk and its stat
        if str(path) == str(gone):
            raise FileNotFoundError(path)
        return real_stat(path, *a, **k)

    monkeypatch.setattr(tiles.Path, "stat", lambda self, *a, **k: flaky_stat(self, *a, **k))
    assert c.evict() > 0
