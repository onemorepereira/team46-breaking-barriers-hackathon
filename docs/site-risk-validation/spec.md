# Site-Risk Validation Places: Spec

**Roadmap:** H8 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H1](../site-risk-sources/spec.md) (licences of the answer-key sources).
**Size:** about 4 days

## Problem
[H4](../site-risk-scoring/spec.md) scores site-risk answers against references. These references don't exist in the repo yet:
- **US:** FEMA's National Risk Index, NOAA Storm Events and the FEMA flood zones are public data, all US federal ([catalog](../site-risk-sources/catalog.md#us-only)) **[ext]**.
- **ADB's region:** no comparable index exists. Past events (cyclone tracks, flood footprints, earthquake shaking) are the closest open evidence **[team]**.

Without a fixed set of places with known answers, a model's site-risk scores can't be compared, as recall couldn't be before the Pecos reference **[team]**.

## Users
- **Primary:** the evaluator (H4) and anyone comparing models on site screening.
- **Secondary:** ADB, who can see the evaluator's evidence for its own places.

## Goals
- **US places:** a validation set with FEMA's index ratings per hazard as the answer key, and NOAA storm events as a check.
- **Asia-Pacific places:** a set with past events after a cut-off date, to back-test whether the levels an answer gives match what later happened.
- Both are stored like reference sets: versioned, licence-checked and snapshotted when tied to a run.

## Non-goals
- **A risk index of our own.** The set uses published ratings and recorded events.
- **Property-level truth.** FEMA's index is tract scale; events are footprints.

## Acceptance criteria
- [ ] **AC1 Format.** A validation place lives in `references/site-risk/<id>/place.json`, with:
  - `id`, `place` (GeoJSON) and `asset_type`;
  - `source` and `licence`, under the reference-set licence rule;
  - `answer_key`: per hazard, a level and its source;
  - `events`: past events with date, hazard, source and the distance to the place.

  The loader refuses a missing licence or a non-commercial one.
- [ ] **AC2 US set.** At least 20 US places across 10 or more states, chosen to span FEMA's ratings (some very low, some very high for flood, hurricane, earthquake, wildfire and tornado). A committed script builds them from OpenFEMA, records the index version (v1.20), and adds NOAA Storm Events within each county since 2015.
- [ ] **AC3 Asia-Pacific set.** At least 15 places in ADB developing member countries, among them Dhaka, Manila, Port Vila, Kathmandu, Karachi, Da Nang and Suva. Each lists past events since 2010 from these sources:
  - IBTrACS tracks within 100 km;
  - Copernicus EMS flood or storm footprints covering the place;
  - USGS ComCat earthquakes of magnitude 5.5 or more within 50 km;
  - the NASA landslide catalog within 10 km.

  There is no answer key for levels here. The events are the evidence.
- [ ] **AC4 Suite.** `prompts/tasks/site-risk/suite.yaml` runs one site-screening task per place, as the ADB T1 suite does. `harness compare` on it gives per-model kappa (US) and event-flag counts (Asia-Pacific).
- [ ] **AC5 Snapshot.** Tying a place to a run copies it, with its sha256, into the run archive, so later rebuilds of the set don't change old scores.
- [ ] **AC6 First run.** The suite is run once with Sonnet. The per-place results and the kappa are recorded in the handoff.

## Success signals
- **Metric (key coverage):**
  - **numerator:** US places with a FEMA index rating for every primary hazard of their asset type;
  - **denominator:** all US places;
  - **target:** 90% or more.
- **Metric (event evidence):** Asia-Pacific places with at least one recorded event since 2010. Reported, not targeted. A place with none is still useful as a "low" check.

## Constraints
- **Licences:** FEMA and NOAA data are US federal (assumed public domain, recorded so). Copernicus EMS footprints carry attribution. DesInventar and EM-DAT are not used: no data licence was found for DesInventar, and EM-DAT is non-commercial ([catalog](../site-risk-sources/catalog.md#multi-hazard-indices-and-loss-records)).
- **Repo:** only metadata and derived summaries (levels, event lists) are committed. No share-alike data.

## What exists today
- **Reference sets and their licence rule:** `references/README.md`, `analysis/reference.py`.
- **Suites:** the ADB T1 suite (`prompts/tasks/adb/`).
- **Snapshotting on tie:** `harness/reference.py`.

## Assumptions and open questions
- **Open:** may ADB supply places it has studied, with its own ratings? *Owner:* Miguel, who asks Clay/ADB. *Default:* the open set only.
- **Assumption:** events since 2010 are fair evidence against hazard layers built before then. Aqueduct v2 and STORM use older records, so the overlap is small. The handoff records each layer's data period.
