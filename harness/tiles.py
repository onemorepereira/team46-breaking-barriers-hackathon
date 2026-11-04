"""The console's tile cache (docs/tile-cache): basemap and result tiles on local disk, and result tiles
in the run's archive.

Lookup order for one tile: a fresh copy on disk, else the run's archive (result tiles), else the upstream
provider, else a stale copy on disk. Upstream URLs come only from `harness.imagery` templates; nothing a
request sends is used as a URL. A response that isn't a JPEG or PNG (providers answer some errors with
HTTP 200 and XML or JSON) is a failure and is never cached.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.store import Store
from harness import imagery

log = logging.getLogger(__name__)

USER_AGENT = "TeamFoundryConsole/1 (+https://github.com/onemorepereira/team46-breaking-barriers-hackathon)"
TIMEOUT_S = 10
MAX_RUN_TILES = 120
RUN_WORKERS = 8
RUN_DEADLINE_S = 45
EVICT_EVERY = 200
DEFAULTS = {"archive": False, "serve": True, "cache_max_mb": 1024, "max_age_days": 30}

Fetch = Callable[[str], bytes]


class TileUnavailable(Exception):
    """No copy anywhere and the provider failed: the endpoint answers 502."""


@dataclass
class Tile:
    data: bytes
    content_type: str
    origin: str  # cache | archive | upstream | stale


def settings(cfg: Any) -> dict[str, Any]:
    return {**DEFAULTS, **(cfg.get("tiles") or {})}


def image_type(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"\x89PNG":
        return "image/png"
    return None


def fetch_upstream(url: str) -> bytes:
    """GET with a 10 s timeout and an identifying User-Agent; raises unless the body is an image."""
    if not url.startswith("https://"):
        raise TileUnavailable("only https:// provider URLs are fetched")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https templates only
        data: bytes = resp.read()
    if image_type(data) is None:
        raise TileUnavailable(f"not an image ({data[:60]!r})")
    return data


class Cache:
    """Files under <out_dir>/tile-cache, least-recently-used eviction by mtime under a size cap."""

    def __init__(self, cfg: Any, fetch: Fetch | None = None, now: Callable[[], float] = time.time) -> None:
        s = settings(cfg)
        self.root = Path(cfg["out_dir"]) / "tile-cache"
        self.max_bytes = int(float(s["cache_max_mb"]) * 1024 * 1024)
        self.max_age_s = float(s["max_age_days"]) * 86400
        self.fetch = fetch or fetch_upstream
        self.now = now
        self._locks: dict[Path, threading.Lock] = {}
        self._guard = threading.Lock()
        self._writes = 0

    # --- paths ---------------------------------------------------------------
    def base_path(self, source: str, z: int, x: int, y: int) -> Path:
        return self.root / "base" / source / str(z) / str(x) / f"{y}.jpg"

    def chip_path(self, index: str, bbox: list[float]) -> Path:
        return self.root / "chip" / index / f"{imagery.chip_key(index, bbox)}.jpg"

    # --- lookups ---------------------------------------------------------------
    def base(self, source: str, z: int, x: int, y: int) -> Tile:
        return self._get(self.base_path(source, z, x, y), imagery.base_url(source, z, x, y), None, None)

    def chip(self, index: str, bbox: list[float], archive: tuple[Store, str] | None = None,
             on_archive_error: Callable[[], None] | None = None) -> Tile:  # fmt: skip
        """archive: (store, key) of the run's archived copy, consulted before the provider."""
        return self._get(
            self.chip_path(index, bbox), imagery.tile_url(index, bbox), archive, on_archive_error
        )

    def _lock(self, path: Path) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(path, threading.Lock())

    def _get(self, path: Path, url: str, archive: tuple[Store, str] | None,
             on_archive_error: Callable[[], None] | None) -> Tile:  # fmt: skip
        with self._lock(path):
            stale: bytes | None = None
            try:
                st = path.stat()
                data = path.read_bytes()
                kind = image_type(data)
                # mtime = when it was fetched (freshness); atime = when it was last used (eviction).
                if kind and self.now() - st.st_mtime < self.max_age_s:
                    os.utime(path, (self.now(), st.st_mtime))
                    return Tile(data, kind, "cache")
                stale = data if kind else None
            except OSError:
                pass
            if archive is not None:
                try:
                    data = archive[0].read_bytes(archive[1]) or b""
                except Exception as e:  # noqa: BLE001 - the archive is a fallback; the provider is next
                    log.warning("tile archive read failed: %s", e)
                    if on_archive_error is not None:
                        on_archive_error()
                    data = b""
                kind = image_type(data)
                if kind:
                    self._save(path, data)
                    return Tile(data, kind, "archive")
            try:
                data = self.fetch(url)
            except Exception as e:  # noqa: BLE001 - provider down, slow, or answered with an error page
                if stale is not None:
                    self._touch(path)  # the only copy while the provider is down: keep it through eviction
                    return Tile(stale, image_type(stale) or "image/jpeg", "stale")
                raise TileUnavailable(str(e)) from e
            kind = image_type(data)
            if kind is None:
                if stale is not None:
                    self._touch(path)
                    return Tile(stale, image_type(stale) or "image/jpeg", "stale")
                raise TileUnavailable("not an image")
            self._save(path, data)
            return Tile(data, kind, "upstream")

    def _touch(self, path: Path) -> None:
        """Mark as just used (atime), keeping when it was fetched (mtime)."""
        try:
            os.utime(path, (self.now(), path.stat().st_mtime))
        except OSError:
            pass

    # --- writes and eviction -------------------------------------------------------
    def _save(self, path: Path, data: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)  # a reader never sees half a tile
            t = self.now()
            os.utime(path, (t, t))  # fetched and used now
        except OSError as e:
            log.warning("tile cache write failed (%s); serving without caching", e)
            return
        with self._guard:
            self._writes += 1
            due = self._writes % EVICT_EVERY == 0
        if due:
            self.evict()

    def evict(self) -> int:
        """Delete least-recently-used tiles until the cache is under 90% of its cap. Returns files deleted."""
        files = []
        for p in self.root.rglob("*.jpg"):
            try:
                st = p.stat()
            except OSError:
                continue  # removed meanwhile (another eviction, or a replace): skip that file only
            files.append((st.st_atime, st.st_size, p))
        total = sum(size for _, size, _ in files)
        if total <= self.max_bytes:
            return 0
        target, deleted = int(self.max_bytes * 0.9), 0
        for _, size, p in sorted(files):
            if total <= target:
                break
            try:
                p.unlink()
                total -= size
                deleted += 1
            except OSError:
                pass
        return deleted


class Archives:
    """The archive a tile request may read, per run: `index.run_uri(run) or archive_uri`, one Store per URI.

    Tile requests sit on the console's shared thread pool, so S3 gets its own tight client (2 s connect, 3 s
    read, 1 attempt), and after any archive error the archive is skipped for BREAKER_S, going straight to the
    provider, so a slow or unreachable S3 can't stall the console."""

    BREAKER_S = 60.0

    def __init__(self, cfg: Any, index: Any, now: Callable[[], float] = time.monotonic) -> None:
        self.cfg, self.index, self.now = cfg, index, now
        self._stores: dict[str, Store] = {}
        self._lock = threading.Lock()
        self.open_until = 0.0

    def store_for(self, run_id: str) -> Store | None:
        if self.now() < self.open_until:
            return None  # breaker open
        uri = self.index.run_uri(run_id) or self.cfg["archive_uri"]
        with self._lock:
            if uri not in self._stores:
                from core.store import FileStore, S3Store

                if uri.startswith("s3://"):
                    import boto3
                    from botocore.config import Config

                    client = boto3.client(
                        "s3", config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1})
                    )
                    self._stores[uri] = S3Store(uri, client=client)
                else:
                    self._stores[uri] = FileStore(uri)
            return self._stores[uri]

    def failed(self) -> None:
        self.open_until = self.now() + self.BREAKER_S


def archive_key(run_id: str, index: str, bbox: list[float]) -> str:
    return f"runs/{run_id}/tiles/{index}/{imagery.chip_key(index, bbox)}.jpg"


def run_chips(run: Any) -> list[tuple[str, list[float]]]:
    """The result tiles a run shows: (index, bbox) per located chip, de-duplicated, first MAX_RUN_TILES."""
    from analysis.judging import measure

    seen: dict[str, tuple[str, list[float]]] = {}
    for x in measure.measure(run).located:
        if x.source != "chip" or not x.bbox:
            continue
        index = x.index if x.index in imagery.CHIP_INDEXES else "s2"
        bbox = imagery.parse_bbox(
            imagery.bbox_text([float(v) for v in x.bbox])
        )  # the endpoint's own rounding
        if bbox is None:
            continue  # outside what the endpoint serves
        seen.setdefault(imagery.chip_key(index, bbox), (index, bbox))
        if len(seen) >= MAX_RUN_TILES:
            break
    return list(seen.values())


def archive_run_tiles(cfg: Any, run: Any, cache: Cache | None = None) -> dict[str, int]:
    """Copy each result tile of a run into its archive (runs/<id>/tiles/…), once. Bounded: MAX_RUN_TILES
    tiles, RUN_WORKERS at a time, RUN_DEADLINE_S overall; tiles pending at the deadline wait for next time."""
    counts = {"fetched": 0, "present": 0, "failed": 0}
    chips = run_chips(run)
    if not chips:
        return counts
    cache = cache or Cache(cfg)
    store: Store = run.store
    present: set[str] = set()
    for index in {i for i, _ in chips}:
        try:
            present |= set(store.list(f"runs/{run.run_id}/tiles/{index}"))
        except Exception:  # noqa: BLE001 - treat as nothing archived yet
            pass
    todo = []
    for index, bbox in chips:
        key = archive_key(run.run_id, index, bbox)
        if key in present:
            counts["present"] += 1
        else:
            todo.append((index, bbox, key))

    def one(index: str, bbox: list[float], key: str) -> None:
        tile = cache.chip(index, bbox)
        if tile.origin == "stale":
            raise TileUnavailable("only a stale copy is available; not archived")
        store.write_bytes(key, tile.data)

    # Not a `with` block: that would wait for every thread. Queued tiles are cancelled at the deadline.
    pool = ThreadPoolExecutor(max_workers=RUN_WORKERS)
    futures = [pool.submit(one, *t) for t in todo]
    done, pending = wait(futures, timeout=RUN_DEADLINE_S)
    for f in pending:
        f.cancel()
    pool.shutdown(wait=False, cancel_futures=True)
    for f in done:
        if f.exception() is None:
            counts["fetched"] += 1
        else:
            counts["failed"] += 1
    if pending:
        counts["skipped"] = len(pending)  # past the deadline: left for the next report
    return counts
