# Scores per District or Hazard Zone: Spec

**Roadmap:** R13 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none. R7 (transfer intervals) adds intervals to each zone row when built; R1 brings zone-sized reference sets in ADB places.
**Size:** about 2 to 3 days

## Problem
The report says scores can be reported per hazard zone or district (Table 7) **[ext]**. ADB acts on places: the Disaster Risk Analytics Explorer decides where to invest in risk reduction, and disaster risk finance decides which areas and sectors come first (Table 5) **[ext]**.

Our reference metrics are one number per run, over the whole area. A run with recall 0.33 might have found every asset in a low-risk district and none in the coastal one where the risk is. The aggregate hides that. An analyst can't tell where a dataset can be trusted without redoing the matching by hand **[team]**.

## Users
- **Primary:** Explorer and disaster risk finance analysts, reading where a dataset is reliable.
- **Secondary:** the LGND/Ode benchmark team, which reports by district.

## Goals
- Every reference metric a run already gets can also be read per zone, from a zone layer whose licence is recorded.
- The zone rows add up to the whole run, so a reader can trust the breakdown.
- Zones with few assets are labelled as such, so a recall of 1/1 isn't read as strong evidence.

## Non-goals
- **Producing hazard layers.** The report puts that out of scope (§2.2) **[ext]**. We only consume zone layers someone supplies.
- **Per-zone judge scores.** The panel judges a run, not a zone.
- **Per-zone T3 or T4 metrics** (R11, R12). They're a follow-up once those exist.
- **Ingesting PCRAFI** before its licence is confirmed.
- **OSM boundaries in the repo.** ODbL is share-alike, and the repo holds none.

## User stories
- As an Explorer analyst, I want recall and precision per district, so that I know which districts' data I can present.
- As a disaster risk finance analyst, I want the same breakdown by hazard zone, so that I can see whether the high-risk zone was covered.
- As the benchmark team, I want per-zone rows in a CSV, so that they join our tables.

## Acceptance criteria
- [ ] **AC1 Zone sets.** A zone set lives in `zones/<id>/`:
  - `zones.json` holds `schema_version`, `id`, `kind` (`district` or `hazard_zone`), `place`, `source` (name, URL, version, retrieved date) and `licence` (the reference-set rule).
  - `zones.geojson` holds Polygon or MultiPolygon features, each with a unique `zone_id` and a `name`.

  The loader refuses any of these, naming the field:
  - a missing licence;
  - a non-commercial licence;
  - a duplicate `zone_id`;
  - a non-polygon feature.
- [ ] **AC2 Tie.** A reference set can name zone sets in `reference.json` (`zones: [<id>, …]`). `harness reference tie <run> <ref> --zones <id>` adds one at tie time. Either way, the zone set is snapshotted, with its sha256, into `runs/<id>/reference/zones/<zone-id>/`. Scoring reads only that snapshot.
- [ ] **AC3 Assignment.** On the reference's grid:
  - **A cell** belongs to the zone containing its centre (the same rule as the area test).
  - **An asset** belongs to the zone holding most of its area cells. A tie goes to the lowest `zone_id` in sort order.
  - **Cells and assets in no zone** go to a row named `unzoned`.
  - **Where zones overlap,** a cell counts in each zone that contains its centre. The zone set is then marked `overlapping`, and the sum check (AC5) is skipped.
- [ ] **AC4 Per-zone metrics.** Each zone row has:
  - the zone's assets, found, missed and flagged cells;
  - cell precision and the zone's base rate;
  - recall, count ratio and lift, under the existing completeness rule: `null` when the reference is incomplete.

  A zone with fewer than 5 assets shows `n < 5` beside its recall and count ratio. Lift is `null` where the zone's base rate is 0.
- [ ] **AC5 Sums.** For a non-overlapping zone set, the zones plus `unzoned` add up to the run's totals: assets, found and flagged cells. A test checks this on the shipped proof, and on a fixture where an asset straddles two zones.
- [ ] **AC6 Shown.** The run page and the static report add a per-zone table under "Against the reference", sorted by recall, lowest first. The map can colour zones by recall. `GET /api/runs/{id}` includes `reference.zones`, a list of rows, empty when the run has no zones. The score and the existing whole-area metrics are unchanged.
- [ ] **AC7 Compare.** `harness compare <suite>` writes `zones.csv`, one row per (run, zone set, zone). Its columns are the AC4 metrics plus `concept`, `place` and `model_key`.
- [ ] **AC8 Licences.** The run's licence list includes each zone set used, with its source and licence, and the presentable verdict counts it.
- [ ] **AC9 First zone set.** A committed script builds the census county subdivisions of Pecos County, TX, from TIGERweb. The Pecos reference names the zone set. The archived Pecos run `79c18997` is re-tied, and its per-zone rows are recorded in the handoff.

## Success signals
- **Metric (breakdown integrity):**
  - **numerator:** tied runs with a non-overlapping zone set whose zone rows sum exactly to the whole-area assets, found and flagged cells;
  - **denominator:** all tied runs with a zone set;
  - **target:** 100%.
- **Metric (hidden spread):**
  - **numerator:** runs whose zone recalls, over zones with at least 5 assets, differ by 0.3 or more;
  - **denominator:** runs with at least 2 such zones.

  This is reported, not targeted. It shows how often the aggregate hides a weak district.

## Constraints
- **Licences:**
  - **PCRAFI** layers are partly non-commercial, and the report has ADB legal confirming their terms (Tables 3 and 16, and its PacRIS reference) **[ext]**.
  - **ADB outputs** exclude non-commercial data (Table 1, §7.4) **[ext]**.
  - **The repo** holds no ODbL or share-alike data (`references/README.md`).
  - **TIGER** is a US government work. The Pecos set records it as *assumed* public domain, because no licence page was found (`references/uspvdb-tx-pecos-v4/reference.json`, `area_licence`). The zone set records the same.
- **Offline and replayable;** no model calls.
- **Small numbers:** small zones give wide intervals (report Table 4) **[ext]**. That's why AC4 labels them, and why R7's intervals plug in later.

## What exists today
- **One set of metrics per run, over the whole reference area:** `analysis/reference.py:283-332`.
- **The grid and the cell-centre area rule:** `analysis/reference.py:154-169`, `:246-249`. Point-in-polygon: `core/geometry.py:32-38`.
- **Asset cells and their caching:** `analysis/reference.py:209-245`.
- **Ties and snapshots:** `harness/reference.py:48-71`. The `reference tie` command: `harness/cli.py:509`.
- **The TIGER county fetch** used to build the Pecos area: `harness/reference.py:80-100`.
- **Search-area boundaries** come from OSM Nominatim or Census TIGER at run time (`harness/area.py:1-13`, `:211`). They're not stored as reusable zones.
- **Per-concept and transfer rows** in compare (`analysis/report.py:197-248`). There's no geographic breakdown.

## Assumptions and open questions
- **Assumption:** "most cells" is a fair rule for an asset that straddles zones. For point assets, it's simply the zone containing the point.
- **Open:** which boundary source outside the US? *Owner:* team. *Default:* geoBoundaries, admin level 2, accepted only where that boundary's own licence passes the loader. Otherwise none.
- **Open:** may PCRAFI hazard or exposure zones be used (report Table 3)? *Owner:* Miguel, who asks LGND and ADB. *Default:* no, until ADB legal confirms commercial use.
- **Open:** is admin level 2 the district level ADB means? *Owner:* Clay/ADB. *Default:* level 2, and a zone set names its level in `kind`.
