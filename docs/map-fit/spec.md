# Map frames the searched area, not its far-flung islands — Spec

**Track:** Quick   **Product stage:** Introduction
**Status:** Built   **Last updated:** 2026-11-05

## Problem
When a run opens or finishes, the map fits to every coordinate of the search area plus the evidence. Some administrative areas include remote parts:
- OpenStreetMap's Netherlands includes Bonaire, Saba and Sint Eustatius in the Caribbean;
- Tokyo's city limits include the Ogasawara islands, about 1,000 km south.

So the map opens at world or ocean zoom with the evidence a few pixels wide (run `5042126d`, "wind farms within Netherlands"). The user asked that a finished run centre on its area.

## Acceptance criteria
- [ ] **AC1 Framing.** The map's fit covers every reported site and imagery result, plus the area's polygons that contain evidence. When no polygon contains evidence, it uses the largest polygon by bounding box. (Size alone failed on Tokyo: its Izu islands boundary is a larger, mostly-sea polygon.) Other polygons are left out of the fit, but they're still drawn. With no area, it fits the evidence only. A pure function `fitCoordinates(view)` in `frontend/src/api.ts` returns the coordinates to fit, and unit tests cover:
  - a Polygon area;
  - a MultiPolygon with a far island;
  - evidence on that far island (it's included);
  - no area;
  - no evidence;
  - a large evidence-free sea polygon against a small one holding the sites (Tokyo).
- [ ] **AC2 Same everywhere.** The fit applies when a run is opened, when a live run finishes, and when "Fit all evidence" is pressed.
- [ ] **AC3 Proof.** In a browser:
  - Netherlands `5042126d` opens framed on the European Netherlands;
  - Tokyo `14f3d7e5` opens framed on Tokyo with its sites;
  - Egypt `1e940baf` and Jodhpur `c71d22e8` are unchanged in framing (single-polygon areas);
  - one live run of a multi-part area ends framed on the main area, checked through the console.

## Non-goals
- No change to the area data, the area outline drawn, or `area_compliance` scoring.
- No fitting during a live run before results exist.

## Plan
1. `api.ts`: `fitCoordinates(view)`, with tests in `api.test.ts`.
2. `Map.tsx`: build the fit bounds from `fitCoordinates(view)` instead of all area coordinates.
3. Build; browser check on the four runs; one live run; handoff.
