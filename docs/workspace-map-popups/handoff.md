# Handoff: workspace map popups and fast run opening

## What changed
- **Imagery on the map** (`frontend/src/Map.tsx`): every imagery result the tools returned shows as a dot while zoomed out (its ~150 m footprint is invisible at county zoom) and as its footprint up close, coloured by inside/outside the requested area. Clicking a dot or footprint opens a popup with the tile, the chip ID, index, observation date, similarity, coordinates, inside/outside, the step it came from (`from T1`) and the imagery source — the details the classic console's panel shows.
- **Locations**: choosing a reported location (marker or list row) zooms in to at least z14, so stacked markers separate, and opens the same popup with the imagery the claim names (`chip naip/obs:…`), else the nearest result within 300 m (`chipFor` in `api.ts`).
- **Thumbnails**: the imagery strip in Findings is clickable; each thumbnail flies to its tile and opens its popup.
- Popups open above the point, and the camera keeps the point low in the frame so the popup isn't clipped. Popup content is built from DOM text nodes, never HTML, since it shows tool output.
- **Opening a run** (`analysis/trace.py`): `Run.load` fetched every archive object one at a time from S3 (~110 ms each; 121 GETs for the Texas parks run). Now the manifest, listing and span chunks are fetched in parallel, all tool results are fetched together on first use (16 at a time), and both — written once each by the agent (`agent/hooks.py`, `agent/archive.py`) — are kept in a bounded (~200 MB) process-wide cache. Span chunks are cached only for finished runs.

## Proof (run against the live console and S3 archive)
| Run | Before | First open | Reopen |
|---|---|---|---|
| Texas parks `815fd905` (1.6 MB view) | 15.1 s | 2.5 s | 1.4–1.7 s |
| Pecos `6d5e9d6b` | 5.9 s | 1.7 s | 1.2 s |
| Jodhpur `36efccf9` | — | 1.7 s | 1.4 s |

Click-to-findings in the workspace, via Previous runs: 2.4 s for the first open and 1.4–1.9 s for a reopen. The rest is the 2.4 MB `run.json` download plus about 0.9 s building the view.

Checked in headless Chromium:
- picking a location opens its popup with the tile, fully in frame;
- clicking a thumbnail opens `naip/obs:268269131`;
- clicking a footprint on the canvas opens `naip/obs:317834394`.

CI checks all pass: ruff, ruff format, mypy, the full pytest suite, the frontend tests (8, including the new `chipFor` test) and the frontend build. New tests: `tests/test_archive_reads.py` (each tool result and span chunk is read once across two opens; the cache is bounded).

## Rulings
- `tests/test_conditions.py` rewrites a tool result in place, which the agent never does. The test now clears the read cache after each rewrite.
- Nearby markers aren't clustered. Zooming in on selection separates them.

## Rollback
Revert the PR. No data or archive format change.

## Later change (2026-11-05)
PR #15's imagery inspector, beside the map, replaced this popup when main was merged into it. The imagery dots (when zoomed out) and clicking a dot or footprint carried over: a click now opens that tile in the inspector. Archived runs still open quickly, since `analysis/trace.py` is unchanged.
