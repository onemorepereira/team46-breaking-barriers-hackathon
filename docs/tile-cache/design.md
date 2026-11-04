# Tile Cache and Archived Result Tiles: Design

**Status:** Current · spec: [spec.md](spec.md)

## Today
- **Basemaps:** `harness/web/static/app.js` (`BASEMAPS`) gives MapLibre four raster sources with upstream URL templates: EOX WMTS `…/s2cloudless-2023_3857/default/g/{z}/{y}/{x}.jpg` (maxzoom 15), USGS `…/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}` (16), NAIP ImageServer `exportImage?bbox={bbox-epsg-3857}…` (19), and OSM `{z}/{x}/{y}.png` (19).
- **Result tiles:** `harness/imagery.py:tile_url(index, bbox)` builds a NAIP `exportImage` URL (index `naip`) or an EOX WMS `GetMap` URL (anything else) for a result's bbox, at 384 px. It's called by `harness/web/view.py:map_layers` (archived runs) and `harness/web/live.py` (live chips). `app.js` puts it in `<img src>` (map popup and tile strip).
- **Archive:** a `Store` (`core/store.py`, `FileStore`/`S3Store`) holds text only (`read_text`, `write_text`, `list`).
- **Reports:** `harness/cli.py:write_report(cfg, run)` is the single path that every finish, judge, re-judge and replay goes through. It already saves the runs-table row (`harness/rows.py`).

## Components

| Component | Change | ACs |
|---|---|---|
| `core/store.py` | `read_bytes(key) -> bytes \| None` and `write_bytes(key, data)` on the `Store` protocol, `FileStore` and `S3Store` (S3 `NoSuchKey` → None) | AC1, AC3 |
| `harness/imagery.py` | Upstream URL builders, the only place upstream hosts appear: `tile_url(index, bbox)` (today's result-tile builder, unchanged name); `base_url(source, z, x, y)` for `s2`, `usgs` and `naip` (NAIP's 3857 bbox is computed from z/x/y: `size = 2πR/2^z`, `minx = −πR + x·size`, `maxy = πR − y·size`, R = 6378137); `BASE_MAXZOOM = {s2: 15, usgs: 16, naip: 19}`; and `console_chip_url(index, bbox, run_id)`, which returns `/tiles/chip/{index}/{w},{s},{e},{n}.jpg?run={id}` with 6-decimal rounding | AC2, AC4, AC5 |
| `harness/tiles.py` (new) | The disk cache plus upstream fetch. `get(cfg, kind, key_parts, url, archive=None) -> (bytes, content_type, origin)`, where origin is `cache`, `archive`, `upstream` or `stale`. `archive_run_tiles(cfg, run) -> {fetched, present, failed}` | AC1–AC3, AC6, AC7 |
| `harness/cli.py:write_report` | Gains `archive_tiles: bool = True`. After the report and row, calls `tiles.archive_run_tiles` when that and `tiles.archive` are true; any exception is logged and swallowed. CLI paths (`run`, `judge`, `replay`) archive synchronously. The console (`live.start_run`, `live.rejudge`) passes `False`, then starts a daemon thread for `archive_run_tiles` after `state.final` is set, so the `done` event is never delayed | AC1 |
| `harness/web/app.py` | Two routes, `GET /tiles/chip/{index}/{bbox}.jpg` and `GET /tiles/base/{source}/{z}/{x}/{y}.jpg`, tagged "Tiles" in `/api/docs` | AC2, AC4, AC5, AC8, AC10 |
| `harness/web/view.py`, `live.py` | `tile_url` becomes `console_chip_url(..., run_id)` when `tiles.serve` is true, and stays the upstream `tile_url` when it's false (rollback). An unknown or missing index maps to `s2`, which matches today's `tile_url`, where any non-`naip` index is EOX | AC2 |
| `harness/web/templates/base.html`, `app.js` | `<body data-tile-proxy="1">` when `tiles.serve` is true (the default). `BASEMAPS` uses `/tiles/base/{id}/{z}/{x}/{y}.jpg` for s2, usgs and naip when the proxy is on; OSM always stays upstream. Attributions unchanged | AC4, AC9 |
| `harness.yaml`, `config.py` | `tiles: {archive: true, serve: true, cache_max_mb: 1024, max_age_days: 30}`. Loader defaults: `archive: false` (tests stay offline), `serve: true` | AC1, AC7 |

## Behavior

**Keys and paths:**
- chip key: `sha1("{index}|{w:.6f},{s:.6f},{e:.6f},{n:.6f}|384")[:20]`;
- disk: `out/tile-cache/chip/{index}/{key}.jpg` and `out/tile-cache/base/{source}/{z}/{x}/{y}.jpg`;
- archive: `runs/{id}/tiles/{index}/{key}.jpg`.

**Threading model:** the two routes are plain `def` endpoints, so FastAPI runs them on its thread pool, never on the event loop, and a 10 s upstream or S3 call can't stall other requests. `harness ui` runs one uvicorn worker (`serve()`), so the in-process per-key lock is enough. The lock dict grows by one tiny entry per distinct tile, which is acceptable at demo scale (thousands of tiles), and is recorded as a known limit.

**Clock and the two timestamps** (design pass 3, the user's call): a tile file's **mtime is when it was fetched** and its **atime is when it was last used**. Both are set explicitly with `os.utime` using the injected clock: on a write, `(now, now)`; on a hit, `(now, mtime)`. Freshness is `now() - mtime < max_age_s`, so a popular tile still refreshes every `max_age_days`. Eviction sorts by atime, least recently used first. `Cache(cfg, fetch=None, now=time.time)`. Tests set times with `os.utime`, never sleep, and inject `fetch`.

**Archive access from tile requests** (design pass 3, the user's call): `tiles.Archives` resolves a run's store once per URI and caches it. For S3 it uses its own client: 2 s connect, 3 s read, `max_attempts: 1`. Any archive read error opens a **breaker for 60 s**, during which tile requests skip the archive and go straight to the provider. The endpoint also skips the archive for a run that is still live (`live.RUNS[run]` not done), since nothing is archived yet. So a slow or unreachable S3 costs at most one 5 s request per minute, and never a stalled tile strip.

**`tiles.get` lookup order:**
1. A disk entry younger than `max_age_days` is served (origin `cache`), and its mtime is touched for LRU.
2. Otherwise, for a chip with `run`, the run's archive. It's resolved as the CLI does it, `index.run_uri(run) or cfg["archive_uri"]`, so a second machine without the index entry still reads the shared archive. A run ID containing `/` or `..` is ignored. If the tile is present, it's copied to disk and served (`archive`). S3 calls use the existing `core.store.s3_config` (5 s connect, 30 s read, 3 attempts in botocore's standard retry mode with backoff), so a slow archive is bounded.
3. Otherwise upstream: `urllib.request` with a 10 s timeout and User-Agent `TeamFoundryConsole/1 (+https://github.com/onemorepereira/team46-breaking-barriers-hackathon)`. The response is accepted only if its status is 200 and its bytes begin with a JPEG (`FF D8 FF`) or PNG (`89 50 4E 47`) signature; EOX WMS and ArcGIS return XML/JSON errors with HTTP 200. It's written atomically (tmp then `os.replace`) and served (`upstream`).
4. If upstream fails and an expired disk entry exists, it's served (`stale`). Otherwise `TileUnavailable` → 502.

**Locking and eviction:**
- A per-key `threading.Lock` (a dict guarded by one lock) stops two requests for one tile from both fetching it.
- Eviction runs after every 200 writes (and once at startup): walk `out/tile-cache`, and if the total exceeds `cache_max_mb`, delete files oldest-mtime-first down to 90% of the cap.

**Validation (AC5):**
- `source` must be in `BASE_MAXZOOM`, with integer `0 ≤ z ≤ maxzoom` and `0 ≤ x, y < 2^z`.
- `index` must be in `{naip, s2}`.
- `bbox` must be 4 finite floats with `−180 ≤ w < e ≤ 180`, `−85.06 ≤ s < n ≤ 85.06` and `e−w ≤ 2`, `n−s ≤ 2` (the user raised it from 0.5°, so large result footprints are served and archived too; detail drops at 384 px, which is accepted).
- `run`, when given, must match `^[A-Za-z0-9-]{1,64}$` (the shape of a run ID); otherwise it's ignored, not an error. It is **not** required to be in the local `out/index.json`: the archive is resolved as `index.run_uri(run) or cfg["archive_uri"]`, so a second machine can read the shared archive.

Anything else returns 404. Upstream URLs come only from `imagery.py` templates.

**Responses:**
- `Content-Type` is `image/jpeg` or `image/png`, sniffed from the bytes on every read (disk, archive or upstream). The `.jpg` file extension is only a name, so a PNG stored under it is still served as PNG.
- `Cache-Control: public, max-age=604800`.
- `X-Tile-Origin: cache|archive|upstream|stale`, for debugging and the tests.

**Archiving at report time (`archive_run_tiles`):**
- The chips come from `measure.measure(run).located`, where `source == "chip"` and the result has a bbox, de-duplicated by key, first 120.
- One `store.list("runs/{id}/tiles/{index}")` per index finds what's already there.
- Missing tiles are fetched through `Cache.chip` (so the disk cache warms too) on a `ThreadPoolExecutor(8)`. The 45 s deadline is `concurrent.futures.wait(futures, timeout=45)`, then `pool.shutdown(wait=False, cancel_futures=True)`: queued tiles are cancelled and the call returns. At most 8 in-flight fetches finish in the background, each bounded by its own timeout. The pool is never a `with` block, because that would wait for every thread on exit. Each fetched tile is written with `store.write_bytes`. A tile whose origin is `stale` is **not** archived, so no archive copy is older than one refetch.
- Bboxes are normalized once, `imagery.parse_bbox(imagery.bbox_text(bbox))`. That rounds to 6 decimals, and the same normalized floats feed the key, the archive path and the upstream URL in both the endpoint and the archiver, so live and archived keys always match.
- **Timeout semantics:** `urllib`'s `timeout=10` applies to each socket operation (connect, then each read). A provider that drips bytes could take longer in total. That's accepted, since tiles are 20–60 KB, and the 45 s deadline bounds archiving as a whole.
- It returns counts, which are printed by `harness replay` and `harness judge`.

## States the user sees

| State | What happens |
|---|---|
| Cached | Tiles appear at once |
| First view, provider up | Same latency as today for a basemap; result tiles of an archived run come from the archive |
| Provider down | Archived chips are served from the archive; basemaps come from the disk cache or a stale copy, or are blank (MapLibre leaves a blank tile and keeps the map usable); OSM is the browser's direct fetch, as today |
| Live run | Chips arrive by streaming, so their tiles come from upstream on first view and from disk afterwards; they're archived when the run's report is written |

## ADRs

**ADR-1: Archive result tiles at report time, not when the agent calls the tool.**
- **Decision:** `write_report`.
- **Options:**
  - (a) inside the agent's hook on AgentCore: rejected, because it adds network fetches to the agent's path, needs a redeploy and slows the run being measured;
  - (b) lazily, on first view: rejected, because nothing would be archived for runs nobody opened, and replay fidelity would depend on someone viewing the run;
  - (c) at report time, which every judge and replay path already passes through: chosen.
- **Cost:** up to 45 s added to the end of a run, typically 1–3 s for 30 tiles.

**ADR-2: Result-tile endpoint keyed by the tile's own parameters, not by a lookup ID.**
- **Decision:** `/tiles/chip/{index}/{bbox}.jpg?run=`.
- **Options:**
  - (a) `/runs/{id}/tiles/{key}`: rejected, because live chips have no archived tile yet and the key alone can't be turned back into an upstream request;
  - (b) parameters in the path, validated and bounded: chosen. It works for live and archived runs, and `run` adds the archive as a fallback.

**ADR-3: Proxy only the imagery basemaps, and leave OSM direct.**
- OSM's tile policy discourages caching proxies and forbids offline use.
- USGS and NAIP are public domain.
- EOX is CC BY-NC-SA and silent on caching. We keep its attribution, and record the non-commercial assumption in the spec.

**ADR-4: A disk cache with LRU by mtime and a size cap.**
- **Options:**
  - (a) in memory: rejected, because it's lost on restart and a restart is common;
  - (b) SQLite blobs: rejected as more machinery than files need;
  - (c) files plus mtime-LRU: chosen, because it's inspectable and deletable.

**Sources:**
- OSM tile policy: operations.osmfoundation.org/policies/tiles (read 2026-11-04);
- EOX license: cloudless.eox.at/documentation/license (read 2026-11-04);
- USGS: usgs.gov/information-policies-and-instructions/copyrights-and-credits (read 2026-11-04);
- upstream cache headers, measured 2026-11-04: EOX `max-age=604800`, USGS basemap `max-age=86400`, NAIP `exportImage` `max-age=43200`;
- WMTS z/y/x order and the NAIP `{bbox-epsg-3857}` form, from the working URLs in `app.js` today.

**Retries:** upstream gets one attempt per request, with no retry loop. On failure the cache serves a stale copy or 502, and the next view of the tile tries again. That avoids retry storms against the providers.

## Failure modes
- S3 slow or unreachable from a tile request: the tight client fails within about 5 s, the breaker opens for 60 s, and the provider serves meanwhile. The batch archiver (report time) uses the normal store config and its 45 s deadline.
- Tiles still pending at the archiver's deadline are reported as `skipped` (not `failed`), and are picked up by the next report.
- A tile is deleted by eviction mid-read: the read raises `OSError`, which is treated as a miss and refetched. A write racing an eviction walk is fine either way, because the bytes are already in memory and served.
- Upstream slow or down: 10 s timeout, then stale or 502; the report-time deadline bounds the archive step.
- Upstream returns an error document with HTTP 200: rejected by the signature check and never cached.
- Disk full: the write fails, the error is logged and the bytes are still served; eviction keeps us under the cap.
- S3 archive unreachable: `archive_run_tiles` counts failures, and the report still writes.
- A concurrent fetch of the same tile: the per-key lock.

## Observability
- `X-Tile-Origin` on every response.
- `archive_run_tiles` counts are printed by the CLI, and logged by the console at warning level when `failed > 0`.

## Migration and rollback
- **Migration:** none. Old runs get tiles archived on their next replay or judge, and `harness replay <id>` archives them on demand. Until then, their chips come from upstream through the cache.
- **Rollback:**
  - `tiles.serve: false` makes the browser use the upstream URLs again, for basemaps (`data-tile-proxy` off) and result tiles (view and live emit upstream `tile_url`);
  - `tiles.archive: false` stops archiving;
  - a revert of the commits restores today's behavior. Archived tiles stay as unused files in the archive, which is harmless, and `out/tile-cache/` can be deleted.
- **One-way doors:** none.

## Implementation plan
1. `Store` bytes API and tests (FileStore, moto S3).
2. `imagery.py` builders and validation, with unit tests (NAIP bbox math against a known tile; bounds).
3. `harness/tiles.py`, with a fake fetcher in tests: lookup order, signature check, stale, lock, eviction.
4. Routes, the view/live URL switch and the `app.js` basemaps. TestClient tests through the real `create_app`, with only `fetch` faked, cover:
   - validation (404s);
   - `X-Tile-Origin` and `Cache-Control`;
   - a warm hit making no fetch (AC8);
   - the 502 path;
   - `tiles.serve: false` emitting upstream URLs;
   - every basemap and chip keeping its attribution (AC9);
   - `/openapi.json` listing both paths under the "Tiles" tag (AC10).
5. Archive at report time, plus a replay-offline test (AC3).
6. Docs (`/api/docs` tag, README line) and a live check: the real console, a cold and a warm basemap, archiving the India run, and the archive serving with upstream blocked.

**Tests, by AC** (CI, with no network: `fetch` or `urlopen` is faked; freshness uses an injected clock and `os.utime`; nothing sleeps):

| AC | Test (file) |
|---|---|
| AC1 | `test_archive_run_tiles_copies_each_result_tile_once` (skips present tiles); `test_archive_bounds_cap_deadline_and_stale_not_archived` (cap via a patched `MAX_RUN_TILES`, a deadline via a patched `RUN_DEADLINE_S` and a fetch gated on a `threading.Event` that's released after the call returns, stale not written); `test_write_report_survives_tile_failures` (through `cli.write_report`); `test_console_archives_after_done` (through `live.rejudge`: `done` is set while a gated `archive_run_tiles` is still blocked) (test_tiles.py) |
| AC2, AC4, AC5, AC8, AC9, AC10 | `test_tile_routes_validate_cache_and_document` (test_web.py, through `create_app`): 404s, `X-Tile-Origin`, `Cache-Control`, a warm hit making no fetch, 502, `tiles.serve: false` emitting upstream URLs, attributions, and the OpenAPI "Tiles" tag |
| AC3 | `test_archive_run_tiles_copies_each_result_tile_once` (second-machine replay with upstream failing) |
| AC6 | `test_upstream_then_disk_then_stale_and_never_an_error_page` (error pages are never cached; stale on failure); `test_fetch_upstream_sends_user_agent_and_timeout` (faked `urlopen`) |
| AC7 | `test_upstream_then_disk_then_stale_and_never_an_error_page` (expired, refetch fails, stale kept); `test_eviction_drops_least_recently_used_tiles_under_the_cap` |
