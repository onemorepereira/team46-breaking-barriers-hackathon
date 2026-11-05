# Hand-Labelled Test Blocks — Spec

**Roadmap:** R2 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none (R1 shares the reference format; no code dependency)
**Size:** L (about 6–8 days: workspace labelling mode, block imagery, builder, loader class)
**Background:** [what the LGND/Ode inception report means for Track 1](../adb-alignment/lgnd-ode-brief.md)

## Problem
Most of ADB's test places have no complete register for the benchmark's concepts. Kathmandu substations, Manila tanks and warehouses, Visakhapatnam tanks and Jodhpur solar have only incomplete OSM data or nothing (Table 14, Table 18) **[ext]**. Without a complete key, an agent run there gets a judged score but no recall (§7.2.1) **[ext]**. Four of the seven `adb-t1-v1` entries are in this position. The report rates "few complete reference sets in ADB countries" a high-impact gap. Its mitigation is complete hand-labelled test blocks of about 1 km, as it did for Nagoya tanks (§3.2 Table 4, §7.4 Table 16, Table 7) **[ext]**. Today that means labelling in an outside GIS tool, tracking each image's licence by hand, and converting the result to our format. Labels traced on non-commercial or view-only imagery may be unusable in ADB outputs (§7.5, Table 17) **[ext]**, and nothing stops that happening.

## Users
- **Evaluators** (primary) who label blocks for a place and concept. They know imagery but aren't GIS specialists.
- **LGND/Ode,** who use the same method and may share or receive blocks.
- **ADB reviewers,** who need each label's imagery and licence on record (Table 1) **[ext]**.

## Goals
- An evaluator can produce, in the workspace, a reference set whose completeness is "complete within blocks", which the scorer uses for recall.
- Every label carries the imagery it was traced on and that imagery's licence. No label can be traced on imagery whose terms bar reuse.

## Non-goals
- **Esri World Imagery, Vantor Open Data and the EOX Sentinel-2 cloudless basemap as labelling imagery.** Esri is view-only, Vantor is CC BY-NC 4.0 (harness/sharp.py:51-56), and EOX cloudless 2023 is CC BY-NC-SA 4.0 (s2maps.eu). EOX stays a viewing layer. Esri and Vantor aren't added.
- **Tracing from OpenStreetMap tiles** (ODbL share-alike; references/README.md, Rules).
- **AI-assisted labelling** (pre-filled candidates from LGND or a vision model). It would bias the key toward what the tools find.
- **Multi-user review workflows, roles or accounts.** One labeller per block. Agreement is measured on demand (Success signals).
- **Segmentation-quality outlines.** A label must touch the right cells. The polygon doesn't need to be exact.

## User stories
- As an evaluator, I want to place test blocks in Kathmandu and mark every substation inside them, so that substation runs get a recall number.
- As an evaluator, I want the workspace to show me only imagery I'm allowed to trace, so that my labels stay usable.
- As an ADB reviewer, I want each block to say who labelled it, when, and on which image.

## Acceptance criteria
- [ ] **AC1 Completeness class.** The loader accepts `completeness: complete_within_blocks`. For it, `area` must be the blocks' Polygon (one block) or MultiPolygon, and `Reference.complete` is true, so recall, count ratio and lift are reported (analysis/reference.py:48-50, 312-317). The run page's reference card shows "complete within N blocks". `complete` and `incomplete` sets behave as before.
- [ ] **AC2 Blocks.** In the workspace (`/workspace/`), a "Label" mode starts a draft with a concept and a place. Each click places a 1 km × 1 km block centred on the click, as the report's blocks are (§7.4 **[ext]**). A draft holds 1 to 25 blocks, and blocks may not overlap. Block edges need not follow cell edges. As for any area, a cell is scored when its centre lies in a block (analysis/reference.py:228-230, 246-249).
- [ ] **AC3 Imagery offered.** For each block, the workspace shows the sharpest allowed image from sources in this order: OpenAerialMap items whose own licence is CC BY or public domain, NAIP, GSI seamless aerial photos (Japan; Table 17 lists them as reusable with attribution **[ext]**), and Sentinel-2 L2A. It is read through `harness/sharp.py` (`candidates`, `read`) at 2,048 px a side, so about 0.47 m per pixel when the source is that sharp. The panel names the source, date, resolution and licence. Vantor and items with NC, ND or SA licences are never offered.
- [ ] **AC4 Labels.** Within a block, the labeller adds a Point or Polygon per asset. A label that crosses the block edge is kept whole. Each label records `ref_id` (draft-unique), imagery source, item id or URL, image date, resolution and licence. The labeller marks a block **done** only after asserting that every asset in it is labelled. A done block may have zero labels.
- [ ] **AC5 Drafts saved server-side.** Drafts are saved through a new API, `PUT /api/labels/{draft_id}`, to the archive at `labels/<draft_id>.json`. They survive a reload. No credentials reach the browser, as for the rest of the workspace (harness/web/app.py:104-107). `GET /api/labels` lists drafts with their block and label counts.
- [ ] **AC6 Build.** `uv run harness reference build-labels <draft_id> --id <ref-id>` writes `references/<ref-id>/` from the draft's **done** blocks only. `area` is their MultiPolygon. `completeness_note` gives the block count, labeller, dates and the concept's definition. `licence` is the team's labels licence (CC BY 4.0), and `source` lists each imagery source used with its licence. BUILD.md lists the blocks. The builder refuses a draft whose labels cite an imagery licence matching the loader's filter (analysis/reference.py:22-25) or a share-alike one, and names the label.
- [ ] **AC7 Proof on a real place.** One set, `hand-kathmandu-substation-v1`, with at least 4 done blocks, ships. The `kathmandu-substations.md` entry in `suites/adb-t1-v1.yaml` gains `reference: hand-kathmandu-substation-v1`. Archived run `5f830bdc` is tied to it, and the run page shows site recall.
- [ ] **AC8 Tests.** A loader test covers `complete_within_blocks` (recall reported; a claim outside every block counts as outside the area). A builder test covers refusing a label traced on a CC BY-NC image, and excluding blocks not marked done.

## Success signals
- **Metric (suite answer-key coverage):** numerator = `adb-t1-v1` entries with a `reference`; denominator = 7. This spec adds at least 1.
- **Metric (label agreement):** on blocks labelled independently by two people, numerator = assets matched by both under any-touch on 160 m cells; denominator = assets labelled by either. Target ≥ 0.85, measured on one double-labelled block before AC7's set ships.
- **Labelling cost recorded:** minutes per done block, from the draft's timestamps, reported in the handoff (the report counts labelling effort as cost, Table 7 **[ext]**).

## Constraints
- **Imagery licences.** Esri is view-only, and traced labels need a terms check (Table 17 **[ext]**). Vantor is CC BY-NC 4.0 (s3://vantor-opendata/LICENSE.TXT). OAM is CC BY 4.0 unless an item says otherwise (harness/sharp.py:7-8). NAIP is public domain. GSI tiles carry the GSI attribution requirement (gsi.go.jp terms of use). Design confirms GSI's terms before it's enabled.
- **Report method:** fully labelled 1 km blocks, scored on 160 m cells (Table 20: 16 blocks, 541 cells **[ext]**).
- **No new runtime dependencies.** Drawing uses MapLibre events already in the map (frontend/src/Map.tsx:315).
- **The repo is written only by the CLI builder,** never by the web server.

## What exists today
- The loader accepts only `complete` or `incomplete`: analysis/reference.py:80-81.
- MultiPolygon areas, and area cells counted by centre, are already supported: analysis/reference.py:94, 143-145, 228-230.
- The workspace is a React and MapLibre app served at `/workspace/` (harness/web/app.py:100-107). Its base layers are EOX Sentinel-2 cloudless, USGS, NAIP and OSM streets (frontend/src/Map.tsx:181-201). It has a click handler but no drawing tools (frontend/src/Map.tsx:315).
- Sharp open imagery lookup, with per-source licences: harness/sharp.py:32, 51-56, 265 (`candidates`), 299 (`read`).
- Reference sets render on the console map as `ref-assets` layers: harness/web/static/adb.js:47-59.
- Ties and suite validation: harness/reference.py:48-63; harness/cli.py:242-247.

## Assumptions and open questions
- **Assumption:** 4 to 16 blocks give a usable recall for a sparse concept like substations. If fewer than 5 assets fall in the done blocks, the set ships with a note saying recall is unstable.
- **Assumption:** OpenAerialMap has sub-metre images over Kathmandu (2015 earthquake response imagery). If AC3 finds none for a block, that block can't be labelled for substations. Move the block, or pick another place for AC7 and record why.
- **Assumption:** blocks are placed before the labeller sees agent results, so the key isn't tuned to a run. BUILD.md records each block's placement time and the draft's first label time.
- **Open:** should block placement be random within the place (unbiased) or chosen where assets are likely (efficient)? — owner: team, with LGND; default: the labeller chooses, and the rule used is recorded in `completeness_note`.
- **Open:** may labels traced on GSI imagery be presented to ADB? — owner: team (Design checks the GSI terms); default: allowed, with attribution, until shown otherwise.
