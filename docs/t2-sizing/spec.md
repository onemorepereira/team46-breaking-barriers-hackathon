# T2 Sizing — Spec

**Roadmap:** R10 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R1 (ADB answer keys with outlines); shares the claims-block extension with R6 · **Size:** M–L (about 7–8 days, plus one live run, about $0.55)
**Background:** [what the LGND/Ode inception report means for Track 1](../adb-alignment/lgnd-ode-brief.md)

## Problem
ADB's exposure base needs to know how big each asset is, not only where it is. Disaster risk finance and damage estimates multiply counts by area or size class (T2 in Table 6; count × area in §5.5) **[ext]**. Our harness scores only where assets are. A site counts as found when its 160 m cell touches the asset. An agent that reports a 2 ha solar farm as 200 ha, or puts a box half a kilometre off the outline, scores the same as one that gets it right. The answer has nowhere to state an outline or an area, so neither can be checked. An analyst who builds a size-weighted exposure layer from an agent's answer has no measure of how wrong the sizes are.

## Users
- **Primary:** ADB analysts building exposure layers, and the LGND/Ode benchmark team, whose T2 workflow (retrieval, then segmentation) agent runs are compared with (Table 9) **[ext]**.
- **Secondary:** the team, extending the suite to T2.

## Goals
- An agent can state, for each site, an outline or box, an area and a size class, each citing the tool evidence it came from.
- Stated outlines are matched to reference footprints with the detector rule (IoU ≥ 0.5, Table 7) **[ext]**. Sizes are scored for area error and size-class accuracy.
- A suite reports the total-area ratio (Σ stated area ÷ Σ reference area), the T2 analogue of count ratio.

## Non-goals
- **A segmentation tool for the agent.** LGND Geo has none. The evaluation measures what agents manage with the tools they have.
- **Changing T1 matching:** any-touch on 160 m cells stays the rule for T1.
- **Damage tiers (T4),** and value or loss per site.
- **A rubric change:** T2 metrics sit beside the score, like the reference metrics.
- **Building ADB outline reference sets:** that is R1. This spec uses the shipped Pecos set.

## User stories
- As an ADB analyst, I want each reported site's size checked against a footprint, so that I know whether its area totals can be used.
- As the benchmark team, I want IoU-matched precision and recall at 0.5, so that agent results line up with detector baselines.
- As an evaluator, I want a T2 suite entry that ties a run to an outline reference, so that sizing is scored without extra steps.

## Acceptance criteria
- [ ] **AC1 Answer contract.** For T2 prompts, the claims block may carry a top-level `sites` list. Each item is `{"lat": num, "lon": num, "outline": GeoJSON Polygon | null, "bbox": [w, s, e, n] | null, "area_m2": num | null, "size_class": str | null, "refs": ["T3", ...]}`. `analysis/provenance.py` parses it, and an item with no `lat`/`lon` is dropped with a recorded reason. When `area_m2` is null, a site's area is the area of its outline, else of its bbox, else null. `claims` is unchanged.
- [ ] **AC2 Reference footprints.** T2 scoring needs a tied reference whose features are all Polygon or MultiPolygon. Otherwise T2 metrics are null, with the note "reference has point features: sizes can't be scored". A reference's area is `projected_area_m2` on the set's local grid. `reference.json` may define `size_classes`, an ordered list of `{"name": str, "max_m2": num | null}` (the last entry has `max_m2: null`). A reference asset's class is the first entry whose `max_m2` is greater than or equal to its area.
- [ ] **AC3 Outline matching.** Sites with an outline or bbox and reference assets in the area are paired by IoU, computed in metres on the reference grid. Pairs with IoU ≥ 0.5 are taken greedily, highest IoU first, one-to-one. Ties are broken by ref_id, then site order. The report gives `iou_precision` (matched ÷ outlined sites inside the area) and `iou_recall` (matched ÷ reference assets; complete references only). It also gives `iou_f1` and `mean_iou` over matched pairs, all to 3 decimals.
- [ ] **AC4 Point matching.** A site with no outline or bbox, but with an `area_m2`, is matched to the unmatched reference polygon that contains its point. Sites are taken in order. These are counted as `point_matched`, are excluded from the IoU metrics, and are included in the area metrics.
- [ ] **AC5 Size metrics.** Over all matched sites with an area, the report gives `area_mdape` (median of |stated − reference| ÷ reference) and `area_within_25` (the share within 25%). Over matched sites that state a `size_class` when the reference defines classes, it gives `size_class_accuracy`. With a complete reference, `area_ratio` = Σ stated area of sites inside the area ÷ Σ reference area, to 3 decimals. Sites without an area count as 0, and the number of such sites is reported.
- [ ] **AC6 Suite and compare.** Suite entries with `task: T2` are accepted. `suites/adb-t2-v1.yaml` holds one entry, `prompts/tasks/adb/pecos-solar-sizing.md` (`concept: solar_farm`, `place: "Pecos County, TX, US"`, `reference: uspvdb-tx-pecos-v4`). `compare.csv` gains `iou_precision`, `iou_recall`, `mean_iou`, `area_mdape`, `area_ratio` and `size_class_accuracy`, and concept rows average them.
- [ ] **AC7 Shown.** The run view's "Against the reference" card gains a "Sizes" line, for example "2 of 5 outlines match (IoU ≥ 0.5); median area error 38%; total area 0.71× reference". The map draws stated outlines over the reference footprints, matched and unmatched styled apart. `GET /api/runs/{id}` returns `sizing`.
- [ ] **AC8 Offline and tested.** All values come from the archive and the reference snapshot, and replay reproduces them. Tests cover identical boxes (IoU 1), disjoint boxes (no match), IoU 0.49 versus 0.51, two sites competing for one asset, point matching, and a reference with points.
- [ ] **AC9 Live proof.** One AgentCore run of the Pecos sizing prompt reports `sites` with areas, and every T2 metric is non-null except where AC2–AC5 make it null. The numbers are in the handoff.

## Success signals
- **Metric (T2 runs scored):** over T2 runs tied to an outline reference:
  - numerator: runs with non-null `iou_precision` and `area_ratio`;
  - denominator: all such runs;
  - target: 100%. Anything less is a contract or parsing gap.
- **Metric (sizes stated):** sites with a non-null area ÷ sites reported, over T2 runs. The target is ≥ 80%. A lower figure means the prompt or tools can't elicit sizes, which is itself a finding for ADB.

## Constraints
- The matching rule for detectors is box overlap at IoU ≥ 0.5 (Table 7) **[ext]**. T2 is outline, measure and grade (Table 6) **[ext]**. Aggregation reports count × area (§5.5, Table 9) **[ext]**.
- Recall-type figures (`iou_recall`, `area_ratio`) need a complete reference (§7.2.1) **[ext]**.
- Polygon intersection needs a geometry library the project doesn't have (`pyproject.toml` lists no shapely). See the open questions.
- USPVDB footprints are public data co-produced by USGS and LBNL (`references/uspvdb-tx-pecos-v4/`, `docs/adb-alignment/handoff.md`). No new licence work is needed.

## What exists today
- T1 matching: a located claim flags its 160 m cell, and an asset counts as found if a flagged cell touches it (`analysis/reference.py:283-335`; asset cells at `:209-225`). Polygons are already accepted as features (`analysis/reference.py:101-103`), and `projected_area_m2` computes planar area on the grid (`analysis/reference.py:252-262`).
- The shipped reference `references/uspvdb-tx-pecos-v4/` has 12 MultiPolygon footprints with a `p_area` attribute.
- Claims are single verbatim values, so there is no outline or size field (`prompts/agent/system.md:12-19`).
- Suite entries default to `task: T1`, and no other task is used yet (`harness/cli.py:234-235`). `suites/adb-t1-v1.yaml` is T1 only.
- LGND tools return chips with a bbox of about the cell size (`tools/lgnd/results.py:28-33`). No LGND tool segments (`tools/lgnd/descriptors.py:13-32`).
- The reference card and layers (`ref-assets-fill`, `ref-assets-line`, `ref-false`) exist in the run view (`docs/adb-alignment/handoff.md`, AC4).

## Assumptions and open questions
- Assumption: without a segmentation tool, agents will mostly state chip boxes and rough areas, so IoU recall will be low. That is the honest result, and it is why point-plus-area matching (AC4) is scored separately.
- Assumption: R6 and R10 both extend the claims block with additive top-level keys (`estimate`, `sites`). Design agrees one parser change for both.
- Open: add `shapely` (BSD-3) for IoU, or rasterise both shapes at 1 m on the reference grid? — owner: user (new dependency); default: add shapely.
- Open: the size classes for solar farms and warehouses? — owner: LGND/Ode; default for solar: small ≤ 10 ha, medium ≤ 100 ha, large above that, defined in the Pecos `reference.json`.
- Open: should a T2 run also be scored on T1 metrics? — owner: team; default: yes, because the `sites` coordinates count as located claims for T1.
