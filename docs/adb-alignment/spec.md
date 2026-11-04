# ADB Alignment: Reference Checks, Licences, Concepts and Transfer: Spec

**Track:** Standard   **Product stage:** Introduction   **Status:** Built ([handoff](handoff.md))   **Last updated:** 2026-11-04
**Background:** [what the LGND/Ode inception report means for Track 1](lgnd-ode-brief.md)

## Problem
LGND and Ode are committed to giving ADB evaluations of geospatial AI with four properties:
- results per asset class;
- results in places the workflow has never seen, reported separately;
- every source and licence recorded;
- scores checked against reference records, using a fixed unit, matching rule and metrics.

They want an agentic rubric that fits beside it. Our harness judges agent runs well, but **none of its results can be put side by side with that benchmark**. It never checks an agent's sites against a reference set, it doesn't group or contrast results by asset class or place, and it doesn't say which data a run relied on or under what licence. For an ADB analyst, that means an agent's dataset can't be compared with the benchmark, can't be broken down by concept, and can't be presented to a government without checking the licences by hand.

## Users
- **Primary:** ADB analysts, and the LGND/Ode benchmark team. They read our results next to their own.
- **Secondary:** the team, running suites and the console.

## Goals
- An agent run can be scored against a **reference set** with the benchmark's unit, matching rule and metrics. Recall is reported only where the reference is complete.
- Every run says **which data and models it used, under which licences**, and whether its result can be shown to third parties.
- Suites carry **concept, place, task and reference** per prompt. `compare` reports **per concept**, with a **transfer gap** between a home and a new place.
- A first reference set with a commercial-use-clean licence ships in the repo, proven on a live run.

## Non-goals
- **No rubric change.** Reference metrics sit beside the score, not in it: the benchmark reports metrics, not a blended score, and PR #7 already bumps the rubric.
- **Measuring the requested *period*:** that belongs to the prompt-compliance work in PR #7.
- **Web search tools** for the agent.
- **Building the embedding benchmark itself:** classifiers, AUROC over a full ranking, labelling-cost curves.
- **Hand labelling.**
- **Ingesting PLATEAU or PCRAFI** until LGND shares a prepared set and its licence is confirmed. The format must accept such a set unchanged.
- **Running the full new suite.** It costs money. One live run proves the path.

## User stories
- As an ADB analyst, I want an agent's sites compared with a reference inventory, so that I know how much it found and how much is right, not only whether it's self-consistent.
- As an ADB analyst, I want to see every data source a run used and its licence, so that I know whether I can present the result.
- As the benchmark team, I want results per asset class and the drop in a new place, so that agent results line up with our tables.

## Acceptance criteria
**Reference sets and metrics**
- [x] **AC1 Format.** A reference set is a directory `references/<id>/` holding `reference.json` and `features.geojson`. `reference.json` has:
  - `schema_version`, `id`, `concept`, `place`;
  - `area` (a GeoJSON polygon or multipolygon covering the extent of the reference);
  - `completeness`: `complete` or `incomplete`, with a sentence on what "complete" covers;
  - `source`: name, URL, version, retrieved date;
  - `licence`: SPDX-style id or a name, URL, the attribution text, and `commercial_use_ok`;
  - `unit`: `asset`;
  - `cell_m`: 160 by default;
  - optionally, `area_source` and `area_licence`: the area's own provenance.

  `features.geojson` holds Point or Polygon features, one per asset. The loader refuses a set with no licence or completeness, one whose `licence.commercial_use_ok` isn't `true`, and one whose licence id or name marks it non-commercial, no-derivatives or academic-only (matched as whole tokens). Its message names the field.
- [x] **AC2 Matching and metrics** (the benchmark's §5.2 and §5.7):
  - **The grid:** the reference area is gridded into `cell_m` cells on a local equal-distance grid anchored at the area's south-west corner.
  - **Flagged cells:** each cell containing one of the run's located claims, where the cell's centre is inside the reference area, is *flagged*.
  - **A found asset:** one of its cells is a flagged cell ("touches" means shares a cell). Each asset counts once.
  - **What's reported:**
    - **site recall** (found ÷ reference assets);
    - **cell precision** (flagged cells touching any asset ÷ flagged cells);
    - **lift** (cell precision ÷ the share of the area's cells that touch an asset);
    - **count ratio** (distinct flagged sites ÷ reference assets, where flagged cells that share an edge or corner merge into one site);
    - the lists of found and missed assets, and false-alarm cells.
  - **Incomplete sets:** recall, count ratio and lift are `null`, with the reason "reference is incomplete"; only precision is reported.
  - **Claims outside the reference area** are counted separately and never scored.
- [x] **AC3 Linking a run to a set.** A run is tied to a reference set by:
  - suite metadata (AC8);
  - `harness run --reference <id>`;
  - or afterwards, by `harness reference tie <run-id> <ref-id>`.

  Tying **snapshots** the set into the run's archive (`runs/<id>/reference/`: the record, the features, and the tie with the reference's sha256). Scoring uses the archive alone, so replay reproduces it with no model call and a rebuilt set never changes an old run's metrics.
- [x] **AC4 Shown where results are read.**
  - **The run page and the static report** show an "Against the reference" card: the reference's name, completeness and licence, and the metrics. A map layer shows the reference features (found and missed) and the false-alarm cells.
  - **`GET /api/runs/{id}`** includes `reference` (null when the run isn't tied).
  - **The score is unchanged.**
- [x] **AC5 A first real set.** One reference set ships in the repo: complete, commercial-use-clean, for a concept the benchmark lists. It's built by a committed, documented script from its public source, so it can be rebuilt. One **live AgentCore run** on its prompt is scored against it, and the metrics are recorded in the handoff.

**Sources and licences**
- [x] **AC6 Data and licences per run.** The run page, the static report and `GET /api/runs/{id}` (`licences`) list everything the run used, each with name, provider, licence, attribution text, URL, and whether commercial use and presentation to third parties are allowed:
  - every **data source** in `datasets_accessed` (the LGND indexes `naip` and `s2`; RODA datasets by ID);
  - the **area-boundary source** (OpenStreetMap Nominatim or US Census);
  - the **reference set**, if tied;
  - the **models**: the agent, every judge, and the narrative model.

  The licence facts come from a sourced table in code, with a URL for each entry. An unknown source is listed as **"licence unknown: check before sharing"**.
- [x] **AC7 Presentable.** A run-level flag: **presentable** when every source is known and allows third-party presentation; otherwise **check before sharing**, listing which sources fail. It appears in the run's KPI strip and the report.

**Concepts, places and transfer**
- [x] **AC8 Suite metadata.** A suite's `prompts` entry may be a file path, as now, or a mapping: `{file, concept, place, task, reference, role}`, where `role` is `home` or `transfer`. Old suites run unchanged. The metadata is stored in each run's manifest (`suite_meta`). A new suite, `suites/adb-t1-v1.yaml`, lists T1 prompts across the benchmark's concepts and places, with the first reference set (AC5) tied to its prompt. It isn't run as part of this effort.
- [x] **AC9 Per concept and transfer.** `harness compare <suite>` adds:
  - a **per-concept table**: runs, mean score and, where tied, mean recall, precision and count ratio;
  - per concept and model, a **transfer gap**: the `home` value minus the `transfer` value, for the score, and for recall when both have complete references.

  Both appear in `compare.html` and in a new `concepts.csv`.

**Docs**
- [x] **AC10** These docs cover the feature, and `tests/test_docs.py` passes:
  - the developer guide (CLI, suite format, reference sets);
  - the judging guide;
  - `gaps.md`;
  - the factory and the docs index.

## Success signals
- The benchmark team can read an agent run's recall, precision and count ratio, in their own units, beside their table, for at least one concept.
- No run result is shared with a source marked "licence unknown".

## Constraints
- **Offline and replayable:** reference scoring and licence listing call no model and no network at read time.
- **Licence rule:** no non-commercial or academic-only reference data in the repo.
- **The rubric file isn't touched;** scores stay comparable.
- **Merging with PR #7** (which touches `view.py`, `report.py` and `measure.py`): additions are new modules and new keys, so the conflicts stay textual.

## Assumptions and open questions
- **Assumption:** a local equal-distance grid of 160 m cells is close enough to the benchmark's grid at city or county scale. *Default:* document the method; matching the benchmark's exact grid needs their cell origin, so ask LGND.
- **Assumption:** the agent's located claims are its flagged sites. A run with no coordinate claims scores recall 0, and precision is undefined.
- **Open:** which concept and place the first set covers. *Owner:* the builder. *Default:* US utility-scale solar from the USGS USPVDB (public domain, if confirmed), for one county the LGND NAIP index covers. The US is a training region in the benchmark, so it proves the machinery; an ADB-place set needs LGND's data.
- **Open:** does LGND share its prepared Nagoya warehouse and tank sets? *Owner:* Miguel, who asks LGND. *Default:* not needed for this effort; the format takes them unchanged.
