# Handoff: the map frames the searched area, not its far-flung islands

Date: 2026-11-05. [Spec](spec.md).

## Cause
The map fitted every coordinate of the search area. Some administrative areas include remote parts:
- OpenStreetMap's Netherlands includes Bonaire, Saba and Sint Eustatius;
- Tokyo's city limits include the Izu and Ogasawara islands.

Runs there opened at world or ocean zoom. It happened on every open, not only when a live run finished.

## What changed
`fitCoordinates(view)` in `frontend/src/api.ts` decides what to frame:
- all reported sites and imagery results;
- plus the area polygons that contain evidence;
- else, the largest polygon.

`Map.tsx` builds its bounds from it, which covers opening a run, a live run finishing, and "Fit all evidence". Outlying parts are still drawn.

The first cut used the largest polygon only. It failed on Tokyo, whose Izu islands boundary is a bigger, mostly-sea polygon. Hence the evidence-first rule.

## Proof (2026-11-05)
- **Unit:** `api.test.ts`, two map-fit tests covering a Polygon, a MultiPolygon with a far island, evidence on the island, no area, no evidence, and the Tokyo case; 20/20 pass.
- **Browser** (`harness ui`), opening archived runs:
  - Netherlands `5042126d` is framed on the European Netherlands (it was world zoom);
  - Tokyo `14f3d7e5` is framed on Tokyo with its five sites (it was Izu islands and ocean);
  - Egypt `1e940baf` and Jodhpur `c71d22e8` are framed on their areas and evidence.
- **Live:** a new run started from the console UI ("Find the wind farms in the Netherlands", run `3847ae55`) finished after 94 s, framed on the European Netherlands.

## Rollback
Revert the PR (frontend only).
