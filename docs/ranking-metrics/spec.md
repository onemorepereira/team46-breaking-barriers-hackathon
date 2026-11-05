# Ranking Metrics: recall@k, AUROC, AP, Review Effort — Spec

**Roadmap:** R4 · **Track:** Standard · **Product stage:** Introduction · **Status:** Built · **Last updated:** 2026-11-05
**Depends on:** none (works on the Pecos set today; R1 and R2 add places)
**Size:** S–M (about 2 days)

## Problem
Our reference metrics score only the sites the agent reported: site recall, cell precision, count ratio and lift. The benchmark compares workflows mainly by how well they rank locations. Its metrics are recall within the top k, AUROC, AP and review effort: how many locations an analyst must inspect to find 50%, 80% or 90% of the assets (§5.7 Table 11, Table 7 scoring) **[ext]**. It uses review effort as its main operational measure of cost (§5.7) **[ext]**. An agent that saw 300 candidates and reported 5 is judged on the 5 alone. We can't say whether its search ranked the real assets high, and we can't put an agent beside the benchmark's tables (Table 19, Table 21) **[ext]**.

## Users
- **Evaluators** reading a run against a reference (primary).
- **LGND/Ode,** who want agent numbers in the units of their Tables 19 and 21 **[ext]**.

## Goals
- Every run tied to a reference shows recall@k, AUROC, AP and review effort to 50/80/90%, computed from the run's own ranked candidates.
- Two runs, or a run and a workflow (R5), can be compared on the same ranking metrics.

## Non-goals
- **Changing the existing metrics** or what counts as flagged. The reported claims stay the flagged set (docs/adb-alignment/design.md:190, 219).
- **Changing the score.** The ranking metrics sit beside it, as the reference metrics do.
- **Calibrating LGND similarities across calls.** Each query's similarity is used only to order within the rule below.
- **Box-overlap (IoU) matching for detectors** (Table 7 **[ext]**): no detector in scope.

## User stories
- As an evaluator, I want to know how many cells an analyst would review, following this run's ranking, to find 80% of Pecos's solar farms.
- As an evaluator, I want recall@k with k equal to the number of asset cells, so that I can read an agent beside the benchmark's warehouse table.

## Acceptance criteria
- [ ] **AC1 The ranking.** A run's ranked candidate list is built from its coordinate claims and each LGND call's own search results (`measure.search_candidates`, which reads each call's raw tool result), deduplicated by 160 m cell, keeping each cell's first entry:
  1. the coordinate claims, in answer order;
  2. then LGND **search results** (the rows that carry a `similarity`; survey grid cells and classifier rows don't, so they are not candidates). Similarities aren't comparable across calls, so each tool call's results are ordered by descending similarity (ties keep first-seen order), and the calls are interleaved round-robin in the order they were made (their call number, `T1`, `T2`, …, assigned when a call starts; results can arrive in a different order when calls run in parallel).

  *(Amended in Design, 2026-11-05: an earlier draft sorted all chips globally and appended chips without a similarity. That would have ranked survey cells and negative classifier rows, and compared similarities across calls.)*

  A candidate's cell is the cell of its lat/lon, the same rule as for claims (design.md:190, ruling 2). Only area cells (centre inside the reference area) are ranked. Every other area cell is unranked and tied at the bottom.
- [ ] **AC2 Positives.** A positive cell is an area cell touched by a reference asset: the `asset_area_cells` set at analysis/reference.py:296. Every other area cell is negative.
- [ ] **AC3 Metrics.** Over the ranking:
  - **recall@k:** assets touched by the top-k ranked cells ÷ reference assets, with any-touch, each asset once. k defaults to the number of positive cells, the benchmark's convention in Appendix B **[ext]**. Also reported at k = 10, 20 and 50.
  - **AUROC:** the probability that a random positive cell ranks above a random negative one, with ties (including the unranked block) counting ½.
  - **AP:** the mean, over positive cells, of precision at the rank where each is reached. Unranked positives contribute 0.
  - **review effort p** for p = 50, 80, 90%: the smallest number of ranked cells whose touched assets reach p of the reference assets. If the list ends first, it's "not reached (x% after y cells)".
  - the **random-order baseline** for review effort: ⌈p × area cells⌉, labelled approximate.
- [ ] **AC4 Completeness.** recall@k and review effort need a complete reference (`complete`, or R2's `complete_within_blocks`) and are null otherwise, with the existing note (analysis/reference.py:316-317). AUROC and AP are reported on incomplete sets with the note "negatives may include unrecorded assets", since the report allows ranking metrics there (§7.2.1 **[ext]**).
- [ ] **AC5 Known answers.** Unit tests on a 10 × 10-cell fixture with 3 single-cell assets:
  - a ranking with the 3 asset cells first gives AUROC 1.0, AP 1.0, and review effort 80% = 3;
  - a ranking with them at ranks 2, 4 and 6 gives AP (1/2 + 2/4 + 3/6) ÷ 3 = 0.5;
  - an empty ranking gives AUROC 0.5, AP 0, and review effort "not reached".
- [ ] **AC6 Shown.** The "Against the reference" card (run page and static report) gains a "Ranking" row: recall@k (with k), AUROC, AP, and review effort 50/80/90 with the random baseline. `GET /api/runs/{id}` returns them under `reference.ranking`. `compare` adds `recall_at_k`, `auroc`, `ap` and `effort_80` to `COMPARE_COLUMNS` (analysis/report.py:118-124) and to the per-concept means.
- [ ] **AC7 Live.** For archived run `79c18997` (Pecos solar, Sonnet on AgentCore, tied to `uspvdb-tx-pecos-v4`), the card shows all four metrics. The handoff records them beside its existing recall of 0.417.
- [ ] **AC8 Speed.** On Pecos (482,799 area cells), the ranking metrics add under 0.5 s to scoring after the first pass. AUROC is computed in closed form from the ranked positions, not by enumerating pairs.

## Success signals
- **Metric (coverage):** numerator = runs tied to a complete reference with non-null `auroc` and `recall_at_k`; denominator = runs tied to a complete reference with at least one asset in the area. Target 100%.
- **Metric (diagnostic value):** numerator = reference-tied runs whose recall@k is higher than their site recall; denominator = reference-tied runs with at least one ranked LGND search result in the area. It's reported once in the handoff, with no target. A non-zero share shows that the ranking finds assets the agent's answer left out, which the claim-only metrics can't show.

## Constraints
- **Report definitions:** the metric names and meanings follow §5.7 Table 11, and review effort at 50, 80 and 90% follows the same table **[ext]**. Cell-level AUROC and AP over 160 m cells match Table 21's setup **[ext]**.
- **Offline and replayable:** computed only from the run's archive and reference snapshot (analysis/reference.py:343-374). No model or network call.
- **No new dependencies** (no scikit-learn); pure Python in `analysis/`.

## What exists today
- Site recall, cell precision, count ratio and lift on claims only: analysis/reference.py:283-335. Called with claims only: analysis/report.py:62-65.
- Each LGND chip's `similarity` is parsed (tools/lgnd/results.py:70) and kept on located results (analysis/judging/measure.py:31, 103-115). Classifier results' `margin` is not kept (tools/lgnd/results.py:42, 70).
- Asset cells and area cells per reference: analysis/reference.py:209-243, 296.
- Compare columns and per-concept means: analysis/report.py:118-124, 197-214.
- The design deliberately chose claims, not chips, as the flagged set: docs/adb-alignment/design.md:219.

## Assumptions and open questions
- **Assumption:** putting claims ahead of unclaimed chips matches what an analyst would review first. If LGND ranks purely by score, AC1 can expose a `chips_only` variant later.
- **Assumption:** the chip centre is a fair stand-in for its footprint. LGND chips can be larger than a 160 m cell, so an asset at the chip's edge is missed.
- **Open:** should a chip flag every cell its bbox touches? — owner: team, with LGND; default: no, centre cell only, to match the claim rule (design ruling 2).
- **Open:** is k = number of positive cells the benchmark's default for every concept? — owner: Miguel (asks LGND); default: yes, per Appendix B, plus the fixed 10/20/50.
