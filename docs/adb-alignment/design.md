# ADB Alignment: Design

**Spec:** [spec.md](spec.md)   **Status:** Agreed   **Last updated:** 2026-11-04

## Shape
| Piece | Where | What it does | Kind |
| --- | --- | --- | --- |
| Reference sets | `analysis/reference.py` | Loads and validates a set; grid, match, metrics | Pure |
| Ties and the builder | `harness/reference.py` | Ties a run to a set (snapshotting the set into the run's archive) and builds the USPVDB set | I/O |
| Scoring a run | `analysis/reference.py` (`from_run`) | Reads the snapshot from the run's own store and scores it | Archive reads only, like `Run.judgement` |
| Licences | `analysis/licences.py` | A sourced table of data, boundary and model licences, and the per-run list | Pure |
| Suite metadata | `harness/cli.py` (`cmd_suite`, `cmd_run`), `harness/invoke.py` (`plan_run(meta=…)`) | Reads and stores concept, place, task, reference and role per prompt | — |
| Per concept and transfer | `analysis/report.py` | `concept_rows`, `transfer_rows`; `compare.html`; `concepts.csv` | — |
| Console and report | `harness/web/view.py` | `run_view()["reference"]`, `["licences"]`, `kpis.presentable` | — |
| | `run.html` and `app.js` | An "Against the reference" card with a map layer, and a "Data and licences" card | — |
| | `report.html` | The same two sections | — |

**Not touched:** the rubric, `analysis/judging/*`, the judge.

## Reference sets (AC1–AC3)
**On disk:**
```
references/<id>/reference.json     # metadata (below)
references/<id>/features.geojson   # FeatureCollection, one Point/Polygon/MultiPolygon per asset, property "ref_id"
references/<id>/BUILD.md           # how it was built (command, source URL, retrieval date)
```
**`reference.json`:**
```json
{"schema_version": 1, "id": "uspvdb-tx-pecos-v4", "concept": "solar_farm", "place": "Pecos County, Texas, US",
 "area": {"type": "Polygon", "coordinates": [...]},
 "completeness": "complete", "completeness_note": "...",
 "source": {"name": "...", "url": "...", "version": "...", "retrieved": "2026-11-04"},
 "licence": {"id": "...", "name": "...", "url": "...", "attribution": "...", "commercial_use_ok": true},
 "unit": "asset", "cell_m": 160}
```
`analysis.reference.load(dir)` validates the record and raises `ReferenceError` naming the field. It refuses:
- a missing `licence`, `completeness` or `area`;
- a `completeness` outside `complete` and `incomplete`;
- `licence.commercial_use_ok` that isn't `true`;
- a licence whose **id or name** contains a whole token `NC` or `ND`, or the words non-commercial / NonCommercial, no-derivatives / NoDerivatives, or academic (see the licence filter below);
- an empty feature set.

`sha256` is computed over the canonical JSON (sorted keys, no whitespace) of the record and of the parsed feature collection, so line endings don't change it.

**The licence filter** matches whole tokens only (SPDX-style): a token `NC` or `ND` bounded by `-`, `_`, a space or the string's edge, or the words `non-commercial` or `academic`. So `CC-BY-NC-4.0` and `CC-BY-ND-4.0` are refused, and `LGND-…` or `ODbL-1.0` are not. `ND` is refused because no-derivatives data can't feed a derived dataset; the spec is updated to say so.

**The grid.** It's a local equirectangular grid anchored at the area's south-west bounding-box corner `(lat0, lon0)`, with `x = R·(lon−lon0)·cos(φm)` and `y = R·(lat−lat0)`, where `R` = 6,371,008.8 m and `φm` is the bounding box's middle latitude. Cell `(i, j)` is `floor(x/cell_m), floor(y/cell_m)`. Over a county, the scale error from one `cos(φm)` is under 1% for an extent of about 1° of latitude. This is documented as an assumption (spec).

**The cells an asset occupies.**
- **A Point** is the cell containing it.
- **A Polygon or MultiPolygon** is every cell that intersects it. That's computed over the polygon's bounding box in cells: a cell is in if a polygon vertex lies in it, or the cell's center or a corner lies in the polygon, or a polygon edge crosses a cell edge. That's the standard exact test for a rectangle against a polygon. Holes are respected through `core.geometry.contains`.

**Flagged cells.** These come from the run's located **claims** (`measure.Located`, source `claim`), not its search chips.
- A claim is scored only if its cell is an **area cell** (centre in the area). So flagged cells, area cells and the asset cells behind the base rate are **one population**, and lift compares like with like.
- Other claims, including one inside the area whose cell centre falls outside it at the edge, go in `outside_area`.
- **"Found"** uses any of the asset's area cells meeting a flagged cell.

**Area cells** (counted once per reference version and process: memoised by sha256). These are the grid cells whose **centre lies in the area** (holes respected, every MultiPolygon part). They're counted exactly with a scanline: for each row, the centre-line crossings of the area's rings give inside intervals, and the cell centres falling in them are counted. That's about rows × edges, a few seconds for a county.

**Assets outside the area.** An asset counts only if at least one of its cells is an area cell. Others are excluded and counted in `assets_outside_area`, and the set's `completeness_note` should explain them.

**Metrics (`analysis.reference.score(ref, claims)`):**
- `found` = assets whose cell set meets the flagged set;
- `missed` = the rest;
- `site_recall` = |found| / |assets|;
- `cell_precision` = |flagged ∩ asset cells| / |flagged|, or null when nothing is flagged;
- `area_cells` = the count of area cells (above);
- `base_rate` = |asset cells that are area cells| / `area_cells`, the same cell set as the numerator;
- `lift` = `cell_precision` / `base_rate`;
- `sites` = connected components of the flagged cells (8-neighbour);
- `count_ratio` = |sites| / |assets|.

When `completeness` is `incomplete`, `site_recall`, `count_ratio` and `lift` are null and `notes` says why. The result also returns `false_alarm_cells` (flagged cells touching no asset) as GeoJSON polygons in lon/lat, plus the found and missed `ref_id`s, for the map.

**The tie, which snapshots the set.** It writes three things to the run's archive (its own store):
- `runs/<id>/reference/reference.json`: the record, as tied;
- `runs/<id>/reference/features.geojson`: the features;
- `runs/<id>/reference/tie.json`: `{"schema_version": 1, "id", "sha256", "tied_at", "by": "suite"|"cli"}`.

So **scoring uses the archive alone**: `analysis.reference.from_run(run, measured)` loads the snapshot through `run.store`, the way `Run.judgement` is read. A rebuilt repo set never changes an old run's metrics, and an S3-archived run scores from any checkout. `stale` is true when the repo's set with that id now has a different sha256. That's informational only: re-tie to adopt the new version.


**When ties happen:**
- `harness run --reference ID` and `cmd_suite` tie **after `plan_run` and before `invoke.execute`**, writing to the plan's archive. So the report and the runs row, written inside `_run_one`, already include it.
- `harness reference tie RUN_ID REF_ID` ties an archived run, then rewrites its report (`write_report`).
- **CLI grammar:** `harness reference {list, tie RUN REF, build-uspvdb --state TX --state-fips 48 --county Pecos --id ID}`, added to `main()`'s handler map.

Scoring runs on every view or report build and reads only the archive and the repo, so it's replayable.

## The first set: USPVDB, Pecos County TX (AC5)
- **The source:** USGS U.S. Large-Scale Solar Photovoltaic Database v4.0 (14 April 2026), `https://energy.usgs.gov/uspvdb/assets/data/uspvdbGeoJSON.zip`.
- **Its metadata:** use constraints "None"; access constraints "None"; completeness "complete for the information presented", with a stated caveat that some facilities absent from the base EIA-860 list are missing.
- **Licence entry:** `{"id": "USPVDB-no-constraints", "name": "USPVDB (USGS and Berkeley Lab): access and use constraints None per its metadata", "commercial_use_ok": true}`. It's co-produced with LBNL, a contractor-run lab, so "U.S. Government work" isn't asserted for the facilities.
- **The area's own provenance:** `area_source` (the TIGERweb layer and GEOID, simplified to 0.0005°, about 50 m) and `area_licence` (Census TIGER, a U.S. Government work, assumed public domain). These optional fields join AC1's record, and the licence list shows them with the reference set.
- **Completeness note:** "Facilities in EIA-860, 1 MW and up, visible in imagery (USPVDB v4.0); USGS notes some facilities outside EIA-860 are missing."
- **The set:** the features with `p_state == "TX"` and `p_county == "Pecos"` (12 in v4.0), keeping their polygons, with `ref_id` = `case_id` and `p_name` / `p_cap_ac` as properties.
- **The area:** Pecos County's official boundary from **US Census TIGERweb** (`State_County/MapServer/1`, `STATE='48' AND BASENAME='Pecos'`, GEOID 48371), a US government work.
  - **Not OSM via Nominatim:** committing that would put ODbL data in the repo.
  - **The difference from a run's area:** the run's enforced area is the OSM boundary, so the two can differ by edge slivers. Claims outside the reference area are counted in `outside_area`, not scored.
- **The builder:** `harness reference build-uspvdb --state TX --state-fips 48 --county Pecos --id uspvdb-tx-pecos-v4` downloads the USPVDB zip and the TIGER county into memory, filters, writes the three files, and prints counts. No download is committed. Tests feed it fixture bytes and a fixture county.
- **The prompt:** `prompts/tasks/pecos-solar.md`, a T1 request: "Find the utility-scale solar farms in Pecos County, Texas, and give each one's location exactly as the tool returned it."

## Licences (AC6, AC7)
`analysis/licences.py` holds `SOURCES: dict[str, Source]`. `Source` has `name`, `provider`, `licence`, `url`, `attribution`, `commercial_use_ok: bool | None` and `presentable: bool | None`, where None means unknown.

| Entry | Licence | Source of the fact |
| --- | --- | --- |
| `lgnd:naip` (USDA NAIP via LGND) | Public domain with attribution | The AWS Open Data registry, `datasets/naip.yaml` `License` |
| `lgnd:s2` (Copernicus Sentinel-2 via LGND) | Free, full and open; notice "Copernicus Sentinel data [Year]" | The Sentinel Data Legal Notice (ESA), registry `sentinel-2-l2a-cogs.yaml` |
| `lgnd` (the LGND Geo service: searches, classifiers, image checks) | **Unknown** (no public terms found) | Ask LGND, so it stays **check before sharing** until then |
| `boundary:osm` (OpenStreetMap through Nominatim) | ODbL 1.0, "© OpenStreetMap contributors" | openstreetmap.org/copyright |
| `boundary:census` (US Census TIGERweb) | U.S. Government work (assumption: no licence page found) | Noted as an assumption |
| `roda:<dataset>` | The dataset's registry `License`, read from that dataset's RODA tool result when present; otherwise **unknown** | The AWS Open Data registry YAML `License` field |
| `model:<key>` (Bedrock models) | "AWS Service Terms (Amazon Bedrock); third-party model terms apply through Bedrock" | aws.amazon.com/service-terms |
| `reference:<id>` | From `reference.json` | The set itself |

`licences.for_run(run, view_inputs)` returns:
- `items`: one per source used, with the role (data, boundary, model or reference) and how it was used;
- `presentable`: true only if every item has `presentable` true;
- `blockers`: the names of the items that aren't presentable.

Data items come from `signals.datasets_accessed` (`lgnd:<index>`; RODA dataset IDs), plus `lgnd` itself whenever any LGND tool ran. The boundary item comes from `manifest.snapshot.search_area.source`. Models come from the manifest (agent), the judgement seats (judges) and `narrative_model`.

**RODA licence extraction:** in the archived tool results of `get_dataset_details`, `preview_dataset` and `sample_dataset` for that dataset ID, find a `License` (or `license`) value in JSON, or a line of text starting `License:`.

## Suite metadata (AC8)
In `cmd_suite`, each prompt is `str | dict`. A dict needs `file` and may carry `concept`, `place`, `task` (default `T1`), `reference` and `role` (`home`, `transfer` or none).
- **Validation:** a `reference` must load; a `role` must be one of those values. Each error names the prompt.
- **Storage:** `plan_run(..., meta=…)` stores `manifest["suite_meta"]`.
- **Tying:** when `meta.reference` is set, the run is tied after `plan_run` and **before `invoke.execute`** (`by: "suite"`), so its report and runs row include the reference.
- **Old suites** (lists of strings) behave the same.

**The new suite, `suites/adb-t1-v1.yaml`:** T1 prompts for the benchmark's concepts and places, using the existing prompt-file style under `prompts/tasks/adb/`:
- warehouses in Nagoya (home) and Gifu (transfer);
- fuel tanks in Nagoya;
- bridges in Metro Manila;
- substations in Kathmandu;
- solar farms in Pecos County, TX, tied to the reference;
- solar farms in Jodhpur.

It runs on **Sonnet only** (7 runs, within `max_runs_per_suite` = 8). It isn't run in this effort.

## Per concept and transfer (AC9)
- **`compare_rows`** gains `concept`, `place`, `role`, `site_recall`, `cell_precision` and `count_ratio`, from `suite_meta` and `analysis.reference.from_run`.
  - These are appended to **`COMPARE_COLUMNS`**, so `compare.csv` gains 6 columns at the end. No in-repo reader depends on the order.
  - `RunReport` gains a `reference` field, filled by `analyze()` through `from_run`. Both live in `analysis/`, so there's no harness import.
- **`concept_rows(rows)`** groups by concept: n, mean score, and the means of recall, precision and count ratio over the runs that have them.
- **`transfer_rows(rows)`** groups by `(concept, model_key)` with at least one `home` and one `transfer` run.
  - Each side's value is the **mean over its runs with a non-null value**, and `n_home` / `n_transfer` count them.
  - `score_gap` = mean home − mean transfer. It's null if either side has no value.
  - `recall_gap` is computed the same way over `site_recall`.
  - Failed or unjudged runs count in n only when they have that value.
  - Runs are **pooled per role** across places, with n reported per side. Place-paired gaps, such as Nagoya→Gifu only, are a follow-up once a concept has several home places.
- **Output:** `compare.html` gets two sections, and `concepts.csv` (concept rows, then transfer rows, with a `kind` column) is written next to `compare.csv`.

## Console and report (AC4, AC7)
- **The API:** `run_view` adds `reference` (the score dict plus the reference's metadata, or null) and `licences` (the `for_run` result). `kpis` gains `presentable`.
- **`run.html` and `app.js`:**
  - An **"Against the reference" card**, shown only when tied: the name, completeness, licence, the metrics (with "n/a: reference incomplete" where null), and lists of found and missed sites.
  - **A map layer** with the reference assets (green when found, red when missed) and the false-alarm cells (orange outline), added to the legend.
  - A **"Data and licences" card**: a table with the name, how it was used, the licence (linked) and presentable (✓, or ⚠ "check before sharing").
  - A **KPI tile**, "Presentable", that reads yes, or "check: <n> sources".
- **`report.html`:** the same two sections as tables, without the map layer.

All text is rendered with `textContent` / Jinja autoescape.

## The claims that get scored
`measure.located` claims, meaning coordinate claims. When the answer has **no claims block** (`prov.claims_block_missing`), the result says "the answer had no claims block, so nothing could be located", distinct from a run that found nothing.

## In-repo callers
- `plan_run(meta=None)` keeps `live.py`'s console runs unchanged.
- `api_docs.py` documents the new `reference`, `licences` and `kpis.presentable` keys in `get_run`'s description.

## Failure modes
| Failure | Handling |
| --- | --- |
| A tie's snapshot is missing or unreadable in the archive | `reference` is `{"error": …}`; the card shows the error; nothing else changes |
| The set is missing from the repo at tie time | `ReferenceError`; the CLI exits non-zero; a suite refuses before any run starts |
| The set changed since it was tied | It's scored, with `stale: true` shown |
| The run has no located claims | recall 0; precision null, with "no located sites to check" |
| A malformed set | `ReferenceError` at tie time (the CLI exits non-zero, and the suite refuses before any run starts) |
| A RODA licence can't be found | The item shows licence unknown, so the run is **check before sharing** |
| The USPVDB download fails in the builder | It exits non-zero with the HTTP error, and nothing is written |

## Migration and rollback
All of this is new files and new keys: `runs/<id>/reference/` (the snapshot and the tie) and `references/`. Old runs have no tie, so `reference` is null and the licences are still computed. A revert removes everything cleanly, and archived ties become unused files. **No one-way doors.**

## Rulings on the last review pass (accepted by Miguel, 2026-11-04)
1. **Lift is null** when cell precision is null (no flagged cells) or the base rate is 0.
2. **A claim flags only the cell holding its lat/lon.** A claim's `bbox`, if any, is ignored.
3. **Precedence for missing values:**
   - an **incomplete** reference gives null recall, count ratio and lift, always;
   - a **complete** reference with no flagged cells gives recall 0 and count ratio 0, with precision and lift null;
   - a missing claims block is scored the same, with its own note first.
4. **Presentable flags:**
   - `boundary:osm` true (attribution required);
   - `boundary:census` true (noted as an assumption);
   - `model:*` true (AWS Service Terms);
   - `lgnd` unknown.
5. **Every run that used LGND reads "check before sharing"** until LGND confirms its terms. This is accepted, and stated in the handoff, with a request to LGND.
6. **The loader requires `licence.commercial_use_ok: true`** (spec AC1 says so).
7. **The licence filter** checks the licence id and name, for the whole tokens `NC`/`ND`, `non-commercial`/`NonCommercial`, `no-derivatives`/`NoDerivatives`, and `academic`, case-insensitive.
8. **"Touches" means shares a cell:** an asset is found when one of its area cells is a flagged cell.
9. **`reference tie` on an archived run** writes to the run's store. An S3 run needs credentials with write access. The tie is written first, then the report; if the report fails, the tie stays, and the next `replay` renders it.

## Performance
Asset cells are computed per polygon as three exact parts, without testing every cell against every edge:
- interior cells, by a centre-line scanline (as for area cells);
- boundary cells, by walking each edge through the grid, sampled at 1/16 of a cell;
- vertex cells.

They're memoised per reference sha256, and area cells likewise. A county-sized set must score in under 1 s after the first view.

## Options considered
| Choice | Picked | Considered, and why not |
| --- | --- | --- |
| Reference metrics in or out of the score | Beside the score | **Adding a measured criterion:** it needs a rubric bump, which collides with PR #7, mixes two kinds of evidence, and the benchmark reports metrics, not a blended score |
| Grid | A local equirectangular grid, 160 m cells, at the area's SW corner | **Web-Mercator tiles:** cell size varies with latitude. **UTM:** needs pyproj, a new dependency, and zone handling. The benchmark's exact grid origin is unknown, so we ask LGND |
| What counts as flagged | Claims | **Search chips:** those are what the agent looked at, not what it delivered; the benchmark scores what the workflow outputs |
| The first set | USPVDB Pecos County | **PLATEAU Nagoya:** licence-compatible, but a multi-GB CityGML extraction, and LGND has a prepared set. **OSM:** incomplete, and ODbL share-alike in the repo |
| Where licence facts live | A sourced table in code | **Fetching at read time:** breaks offline replay |

## AC map
| AC | Where |
| --- | --- |
| 1 | `analysis.reference.load` |
| 2 | `analysis.reference.score` |
| 3 | `harness.reference.tie`/`tied`, `cmd_run --reference`, `cmd_reference`, `cmd_suite` |
| 4 | `view.run_view`, `run.html`/`app.js`, `report.html` |
| 5 | `harness reference build-uspvdb`, `references/uspvdb-tx-pecos-v4/`, a live run |
| 6, 7 | `analysis.licences`, view, report, KPI |
| 8 | `cmd_suite` and `plan_run(meta)`, `suites/adb-t1-v1.yaml` |
| 9 | `report.concept_rows`/`transfer_rows`, `compare.html`, `concepts.csv` |
| 10 | The developer guide, the judging guide, gaps, the factory, the index |
