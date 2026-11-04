# Tile Cache and Archived Result Tiles: Handoff

**What shipped** (branch `design/eval-harness`, 2026-11-04):
- **Result tiles are archived.** The imagery under each search result is saved in the run's archive (`runs/<id>/tiles/`) when its report is written. In the console that happens in the background after `done`.
- **The console serves the tiles.** It serves result tiles and the Sentinel-2, USGS and NAIP basemaps from a disk cache (`out/tile-cache/`), going to the archive and then the provider on a miss. OpenStreetMap still loads directly, per OSM's tile policy.
- **Archived runs replay their imagery offline.**

**Verification:**
- **Suite:** `uv run pytest` gives 146 passed (145 at first, three runs in a row, plus the Verify-fix test). `ruff check .` and `mypy` are clean.
- [x] **AC1 Archived at report time, bounded.**
  - Tests:
    - `test_archive_run_tiles_copies_each_result_tile_once` (archived once; already-present tiles skipped);
    - `test_archive_bounds_cap_deadline_and_stale_not_archived` (120 cap patched to 1; the deadline returns with gated fetches pending, counted as skipped; a stale-only tile isn't archived);
    - `test_write_report_survives_tile_failures` (through `cli.write_report`);
    - `test_console_archives_after_done` (through `live.rejudge`: `done` and the full view are set before the gated archiver runs).
  - **Live:**
    - `harness replay a9a69e76…` (India, local archive) archived 31 tiles, 788 KB, in 2.5 s; a second replay fetched nothing.
    - `harness replay daa193db…` (AgentCore run, **S3** archive) gave `{'fetched': 23, 'present': 0, 'failed': 2}` in 27 s. The 2 were transient NAIP slowness and fetched in about 1.5 s on retry. The next replay completed the set, and `aws s3 ls` shows 25 tiles under the run's `tiles/`.
- [x] **AC2 Served by the console, nearest copy first.**
  - Test: `test_tile_routes_validate_cache_and_document` (the view emits `/tiles/chip/…?run=`; the archive is served with `X-Tile-Origin: archive`).
  - **Live:** in headless Chromium on the running console, the India run page loaded all 31 result tiles (lazy-loaded ones forced) with **0 non-200 tile responses**. It made 18 basemap requests, all 200 through `/tiles/base`, and contacted **no third-party hosts** (Sentinel-2 is the default basemap).
- [x] **AC3 Replay without providers.**
  - Test: `test_archive_run_tiles_copies_each_result_tile_once` (a second machine with upstream failing serves every tile from the archive).
  - **Live:** a second console (port 8788) ran with an empty tile cache, only this run in its index, and `https_proxy=http://127.0.0.1:9` (every outbound HTTPS refused). It returned **31/31 result tiles, all with origin `archive`**.
- [x] **AC4 Basemaps cached on our server.** Live, cold then warm:

  | Basemap | Cold | Warm |
  | --- | --- | --- |
  | s2 | 512 ms (`upstream`) | 1.4 ms (`cache`) |
  | usgs | 558 ms | 1.1 ms |
  | naip | 58 ms | 1.2 ms |

  OSM is left on its direct URL in `app.js`, and `/tiles/base/osm/…` returns 404.
- [x] **AC5 No open proxy.** `test_tile_routes_validate_cache_and_document` checks six refused URLs (OSM, over max zoom, x out of range, unknown index, wider than 2°, not a bbox): all 404, and **the provider was called 0 times**. `test_inputs_are_validated_before_any_url_is_built` adds a hostname as the source. `fetch_upstream` refuses non-`https://` URLs (test).
- [x] **AC6 Failure behavior.** `test_upstream_then_disk_then_stale_and_never_an_error_page` covers stale on failure, XML/JSON error pages with HTTP 200 rejected and never cached, and TileUnavailable → 502 (also through the route). `test_fetch_upstream_sends_user_agent_and_timeout` covers the User-Agent and `timeout=10`. `test_archive_breaker_skips_the_archive_after_an_error` covers the 60 s breaker. Live, an uncached basemap with the provider blocked gave 502 in 6 ms.
- [x] **AC7 Bounded disk.** `test_eviction_drops_least_recently_used_tiles_under_the_cap` evicts by atime, oldest first. Expired tiles are refetched, and kept when the refetch fails (the first AC6 test). Freshness and last use are separate timestamps: mtime is when a tile was fetched, atime when it was last used.
- [x] **AC8 Fast when warm.** In CI, a warm hit makes no fetch and carries `Cache-Control: public, max-age=604800`. Live, warm tiles took 1.1–1.7 ms (target < 20 ms).
- [x] **AC9 Attribution unchanged.** The route test checks that the EOX, USGS and OSM credits are in `app.js` and that every chip carries `tile_source`.
- [x] **AC10 Docs.** OpenAPI lists both paths under the "Tiles" tag (test), with descriptions, the origin header and the 404/502 responses.

**Verify review** (independent subagent: ran the suite itself, 145 passed, ruff and mypy clean): **no blockers**. These minor findings are fixed:
- the cache now also evicts at startup (the every-200-writes count is per process);
- one vanished file no longer aborts an eviction pass (test);
- a stale copy served while the provider is down is marked used, so eviction keeps it;
- a bbox the endpoint would refuse keeps its provider URL (test), as today;
- re-judging an archived run no longer turns off its archive fallback.

Its S3 question was checked live: with our role, a missing tile key returns "not found" (`NoSuchKey` → None), not 403. An unarchived tile therefore doesn't trip the breaker. Accepted as is:
- The AC9 test checks the credit strings, not their rendering. The screenshots show the attribution control.
- Fetches already in flight run past the 45 s deadline, bounded by their own timeouts. This happens only in the background and in the CLI.
- Any well-formed run ID falls back to the default archive. This is localhost only.

**Exercised live:** the console at 127.0.0.1:8787 and an offline twin at :8788, both above. Replay ran against the local and S3 archives.

**Security scans:**
- **bandit 1.8.6** (`bandit -r harness/tiles.py harness/imagery.py harness/web/app.py core/store.py`):
  - B324 (SHA-1) is fixed with `usedforsecurity=False`; it names cache files only.
  - B310 (`urlopen` schemes) is accepted: URLs come only from fixed `https://` templates, and `fetch_upstream` now refuses anything else (tested).
  - The two B110s (`except: pass`) are accepted as intentional fallbacks.
- **Secrets:** the grep on the diff for AWS key, secret and session-token patterns gave 0 hits.
- **Dependencies:** none added.

**Gate history:**
- **Define:** self-review, clean.
- **Design:** 3 subagent passes. Pass 1 found 9 blockers, all resolved: thread model, live `done` delay, archive resolution, `None` index, S3 timeouts, rollback for chips, AC tests, clock, PNG. Pass 2 found 3: run-ID shape vs index membership, deadline enforcement, named tests. Pass 3 found 2: freshness vs LRU on one mtime, and S3 stalling the request path. Those went to the user, who chose to split the timestamps and to use a tight S3 client plus a breaker. The user also raised the bbox limit from 0.5° to 2°.
- **Build:** each slice was green. The new background-archive test caught a real race (archiving started before `done` was set), fixed by starting it after the `finally`.
- **Verify:** see the Verify review below.

**Specialists consulted:** SRE/Platform (timeouts, breaker, no retry storms, bounded archiving), AppSec (allowlist, no request-derived URLs, https-only, localhost assumption), Frontend (basemap switch, lazy images, attribution), QA (no sleeps; injected clock and `os.utime`; real entry points with only the provider faked).

**Decisions and deviations:**
- `tile_url` kept its name; the design first proposed a rename.
- The CLI prints tile counts only when something failed or was skipped, to keep replay quiet.
- The bbox limit is 2°, not 0.5° (the user's call).

**Rollback:**
- `tiles.serve: false` sends basemaps and result tiles straight to the providers again.
- `tiles.archive: false` stops archiving.
- A revert restores the old behavior. Archived tiles stay as unused files, and `out/tile-cache/` can be deleted.

**Follow-ups:**
- Existing runs get their tiles on their next replay or judge. `for id in …; do harness replay $id; done` backfills them.
- The per-key lock map grows by one entry per distinct tile. That's fine on localhost at demo scale, but it needs bounding before the console is ever exposed beyond 127.0.0.1.

**Risks to watch:**
- EOX tiles are cached under CC BY-NC-SA, which assumes non-commercial use (spec assumption).
- Upstream slowness, NAIP especially, shows up as `skipped` or `failed` counts on replay.
