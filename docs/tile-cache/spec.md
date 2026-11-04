# Tile Cache and Archived Result Tiles: Spec

**Status:** Built

## Problem
Every map image in the console is fetched by the viewer's browser straight from a third-party provider (EOX, USGS/NAIP, OpenStreetMap), and nothing is kept anywhere except the browser's own HTTP cache. As a result:
- an archived run's result tiles can't be shown when the providers are down or offline, so the console can't replay a run from the archive alone, which is the harness's founding rule;
- a slow provider, NAIP especially, makes the tile strip and the basemap slow on every new browser, machine or cleared cache.

The people affected are the team and the ADB reviewers watching a demo, often on conference Wi-Fi.

## Users and job
A demo operator opens a run (live or archived) and expects its map, imagery basemap and result tiles to appear fast, and to keep appearing for archived runs regardless of provider availability.

## Acceptance criteria
- [x] **AC1 Result tiles are archived.** When a run's report is written (on finish, judge, re-judge and replay; in the console's live runs this happens in the background after the run's `done` event, so it never delays the result), each result tile it shows (the result's bounding box, from the NAIP or Sentinel-2 cloudless source) is fetched once and stored in the run's archive as `runs/<id>/tiles/<index>/<key>.jpg`. Tiles already archived are not fetched again. The work is bounded: at most 120 tiles per run, 8 at a time, a 10 s timeout per tile, and a 45 s deadline per run. It is on when `tiles.archive: true` (set in `harness.yaml`), and a failure never fails the report.
- [x] **AC2 Result tiles are served by the console, from the nearest copy.** The console's run view and live stream point every result tile at `/tiles/chip/{index}/{bbox}.jpg?run=<id>`, never at a third-party URL. The endpoint answers from the local disk cache, else the run's archive, else the upstream provider, and saves what it fetches in the disk cache.
- [x] **AC3 Replay without the providers.** With every upstream fetch failing, an archived run whose tiles were archived still serves all of them (test).
- [x] **AC4 Imagery basemaps are cached on our server.** The Sentinel-2 cloudless, USGS imagery and NAIP basemaps load through `/tiles/base/{source}/{z}/{x}/{y}.jpg`, cached on disk under `out/tile-cache/`. The OpenStreetMap streets layer stays a direct browser fetch: OSM's tile policy discourages caching proxies and forbids offline use.
- [x] **AC5 No open proxy.** The endpoints build upstream URLs from fixed templates only. A `source` or `index` outside the allowlist returns 404. So does a z/x/y out of range or above the source's max zoom, or a bbox that is malformed, out of range or wider than 2° on a side (raised from 0.5° at the user's call, so every LGND result tile is served). No request parameter is ever used as a URL or host.
- [x] **AC6 Failure behavior.** Upstream calls have a 10 s timeout and send an identifying `User-Agent`. A response that isn't an image (an XML or JSON error with HTTP 200) counts as a failure and is never cached. On failure, a stale cached copy is served if one exists; otherwise the endpoint returns 502 and the map shows a blank tile.
- [x] **AC7 Bounded disk.** The disk cache is held to `tiles.cache_max_mb` (default 1024) by evicting the least recently used tiles. Eviction runs every 200 writes, so the cache can exceed the cap by at most 200 tiles (about 5 MB) between passes. Entries older than `tiles.max_age_days` (default 30) are fetched again, and kept if the refetch fails.
- [x] **AC8 Fast when warm.** A cached tile is served with `Cache-Control: public, max-age=604800` and no upstream call (CI test), in under 20 ms at the running console (measured in Verify, not timed in CI).
- [x] **AC9 Attribution unchanged.** Every basemap and result tile keeps its on-map attribution (EOX CC BY-NC-SA, USGS public domain, © OpenStreetMap contributors).
- [x] **AC10 Docs.** `/api/docs` documents both endpoints, and the handoff records the source and license terms.

## Non-goals
- Showing the exact pixels LGND analysed: LGND's tools return no image.
- Prefetching basemap tiles a user isn't viewing (bulk download; OSM forbids it, and it's wasteful elsewhere).
- Caching OpenStreetMap tiles.
- Sharing the disk cache across machines. It lives in the local `out/`; the archive is the shared copy.

## Constraints
- **OSM tile policy:** it does not recommend a caching proxy in front of `tile.openstreetmap.org`, does not permit offline use, and requires a clear User-Agent (operations.osmfoundation.org/policies/tiles, read 2026-11-04).
- **EOX Sentinel-2 cloudless:** CC BY-NC-SA 4.0 for non-commercial use, with attribution kept visible. Its terms say nothing about caching (cloudless.eox.at/documentation/license, read 2026-11-04).
- **USGS (NAIP, The National Map):** U.S. public domain (usgs.gov copyrights-and-credits, read 2026-11-04).

## Assumptions and open questions
- The console binds to 127.0.0.1 only (`serve()`), so the unauthenticated tile endpoints aren't reachable from other machines. Exposing the console on a network would need a rate limit and a bounded lock map first. Owner: team. Default: localhost only.
- Keeping a local copy of EOX tiles for viewing, under the same attribution, fits CC BY-NC-SA's non-commercial use. A hackathon evaluation is non-commercial. Owner: team. Default: proceed, and drop EOX from the server cache if commercial use is ever planned.
- Archived result tiles total about 1–3 MB per run (≤ 120 × ~25 KB at 384 px). Owner: team. Default: accept; measured in Verify.

## Success signal
In a fresh browser, an archived run's tile strip loads with the providers blocked, and the time to the first basemap tile drops on the second machine-visit.
