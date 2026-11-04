# Reference sets

Each folder holds one reference inventory that agent runs can be scored against
([docs/adb-alignment](../docs/adb-alignment/spec.md)):

| File | Holds |
| --- | --- |
| `reference.json` | id, concept, place, area (GeoJSON polygon), completeness, source, licence, unit, cell size, and the area's own source and licence |
| `features.geojson` | One Point, Polygon or MultiPolygon per asset, with a `ref_id` property |
| `BUILD.md` | How it was built and from what, so it can be rebuilt |

**Rules** (the loader enforces them):
- **Licence:** commercial use must be allowed. No NC, ND or academic-only licences.
- **Completeness:** must be `complete` or `incomplete`. Recall is reported only for complete sets.
- **Area data:** no ODbL or other share-alike data in the area or the features. This repo is Apache-2.0.

| Set | Concept | Place | Assets | Source |
| --- | --- | --- | --- | --- |
| `uspvdb-tx-pecos-v4` | Utility-scale solar | Pecos County, TX, US | 12 | USGS USPVDB v4.0; US Census TIGER county |
