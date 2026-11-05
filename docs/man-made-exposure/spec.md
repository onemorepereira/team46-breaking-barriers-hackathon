# Man-Made and Technological Exposure: Spec

**Roadmap:** H6 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H2](../hazard-tools/spec.md) (the hazard server it extends).
**Size:** about 4 days

## Problem
The question names man-made disasters too **[team]**. These include:
- a dam upstream;
- a chemical plant or refinery next door;
- a pipeline through the site;
- a power plant's exclusion zone;
- recurring conflict.

The open sources that cover them have mixed licences ([catalog](../site-risk-sources/catalog.md#infrastructure-man-made-hazards-and-conflict)) **[ext]**:
- **Usable as is:** the WRI power plant database is CC BY but unmaintained since 2022. Global Dam Watch is CC BY. UCDP is CC BY 4.0.
- **With conditions:** OSM is share-alike, and the Global Energy Monitor trackers need their commercial terms confirmed.
- **Not usable:** ACLED needs a paid public-sector licence for ADB.

## Users
- **Primary:** the agent answering a site-screening task, and the developer reading it.
- **Secondary:** the evaluator, which checks the distances and counts.

## Goals
- The agent can list man-made hazard sources near a place, with distance and direction:
  - dams upstream within 50 km, with reservoir size;
  - power plants and industrial sites within 10 km, by type;
  - pipelines and major lines within 1 km;
  - conflict events within 25 km over the last 5 years.
- Each row names its source, and the answer can rate a `man_made` hazard level from them.

## Non-goals
- **Dam-break modelling.** The tool reports that a dam is upstream and how big it is, not a flood wave.
- **News-based risk scoring.** GDELT is noisy, so it is left out of the first release.
- **ACLED.** It is excluded by licence.

## Acceptance criteria
- [ ] **AC1 Tool.** `man_made_near(lat, lon, radius_km?)` returns rows with `kind`, `name`, `distance_km`, `bearing_deg`, `attributes` and `source_id`. The kinds are `dam`, `power_plant`, `industrial`, `pipeline`, `power_line` and `conflict_event`.
- [ ] **AC2 Upstream.** A dam counts as upstream when it lies in the place's upstream basin (HydroSHEDS, whose licence allows commercial use), not merely within the radius. A test covers a dam that is near but downstream.
- [ ] **AC3 Sources.** The first release uses:
  - Global Dam Watch v1;
  - the WRI power plant database, labelled with its last update (2021);
  - UCDP GED;
  - OSM industrial, pipeline and power features via Overpass, queried live and not stored.

  A Global Energy Monitor tracker is added if H1 clears its terms.
- [ ] **AC4 Share-alike.** OSM results are used in the answer and archived in the run (private), but never published as a dataset. The run's licence list shows ODbL.
- [ ] **AC5 Levels.** `levels.yaml` (H3) gains `man_made` thresholds, cited or tagged **[team]**: for example a large dam upstream within 20 km, or a refinery within 2 km, is `high`.
- [ ] **AC6 Known answers.** Fixture tests cover:
  - a dam upstream;
  - a dam downstream;
  - an empty result at sea;
  - a conflict event exactly at the radius.

## Success signals
- **Metric (grounded):**
  - **numerator:** man-made items in answers that match a tool row;
  - **denominator:** all man-made items in answers;
  - **target:** 95% or more.

## Constraints
- **Licences:** as above, gated by H1.
- **Staleness:** the power plant database's age is shown with every row from it.

## What exists today
- None beyond H2's server.

## Assumptions and open questions
- **Open:** may conflict events appear in an ADB answer at all, or only as "see a specialist"? *Owner:* Clay/ADB. *Default:* counts and dates only, no actor names.
