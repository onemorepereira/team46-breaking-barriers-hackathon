# Ranking Metrics — Design

**Spec:** ./spec.md   **Last updated:** 2026-11-05
**Status:** Current

## Overview
`analysis/reference.py` gains a pure function that builds a run's ranked candidate cells and scores them against the reference.
- **Ranking:** claims in answer order, then LGND search results, each call ranked by its own similarity and the calls interleaved round-robin. It's deduplicated by 160 m cell, area cells only (spec AC1).
- **Metrics:** recall@k, AUROC, AP and review effort to 50/80/90%, plus a random-order baseline for review effort. All are computed in one pass over the ranked list, with closed-form counts for the unranked cells, so Pecos's 482,799 area cells cost nothing extra.
- **Where it plugs in:** `from_run` adds the result as `reference["ranking"]`, so the API, the classic console card (`adb.js`), the static report, the workspace and `harness compare` all read it from the same place.
- **Replay:** it is computed from the run's archive and the tied reference snapshot only, so replay reproduces it.

## Experience
**The reference card** ("Against the reference": classic console `adb.js`, static report `analysis/templates/report.html`, workspace "Independent reference benchmark" in `frontend/src/Evaluation.tsx`) gains a **Ranking** row:
- `recall@k` with its k ("Recall@k (k = 23 asset cells)");
- `AUROC`, `AP`;
- `Review effort to 50% / 80% / 90%`, each "N cells (random ≈ M)", or "not reached (x% after y cells)".
Tooltips:
- **Recall@k:** "Share of reference assets touched by this run's top-k ranked cells".
- **AUROC:** "How often an asset cell ranks above an empty one (0.5 = random)".
- **AP:** "Average precision down this run's ranking".
- **Review effort:** "Cells an analyst would review, in this run's order, to find that share of the assets".

**States:**
- **Complete reference:** all metrics shown.
- **Incomplete reference:** recall@k and review effort show "Not defined", plus the note "negatives may include unrecorded assets" for AUROC/AP.
- **No candidates in the area:** AUROC 0.5, AP 0, effort "not reached", and the note "no ranked candidates inside the reference area".
- **No assets in the area:** all metrics "Not defined".
- **Untied run:** no card, as today.

Workspace layout reuses the existing `Stat` tiles in the reference section, so there's no new component.

## Architecture
- **`analysis/reference.py`:**
  - **`Candidate = tuple[float, float, float, str]`:** (lat, lon, similarity, the tool call's `ref`). Only LGND **search results** are candidates: rows from `matches` carry a `similarity`, while `cells` (survey views) and `results` (classifier output) don't (tools/lgnd/results.py:37-73). They come from **`analysis/judging/measure.py:search_candidates(run)`**, which walks each successful LGND span's own result (`chips_of`) and keeps rows with a numeric similarity, tagged with the span's `harness.tool.ref`. It does not use `m.located`: that list deduplicates places across calls (measure.py:91-101), so a place a later call ranked first would carry the earlier call's rank.
  - **`rank_cells(grid, area, claims, chips) -> list[Cell]`** (AC1):
    - **Claims:** iterate claims in answer order.
    - **Per call:** group chips by their call, in first-seen call order. Stable-sort each group by `-similarity`, so ties keep first-seen order.
    - **Call order:** the calls are ordered by call number (`T<n>`, assigned when a call starts, agent/hooks.py:219-221), not by result arrival, which differs for parallel calls. Refs without a number (the `T?` fallback, hooks.py:263) go last, in arrival order.
    - **Interleave:** round-robin, depth by depth (ADR-4).
    - **Each candidate:** take `grid.cell(lon, lat)`; skip it if it isn't an area cell (`in_area`) or is already taken.
  - **`_ranking(...)`** builds the cell → assets map from `occupied` and calls **`ranking_metrics(ranked, cell_assets, n_assets, positives, area_cells, complete) -> dict`** (AC3, AC4), which is pure and unit-tested. Over the ranked list:
    - **P, N:** `P = len(asset_area_cells)`, `N = area_cells - P`.
    - **Cell → assets:** a map from each ranked cell to the reference assets whose cells include it (`occupied`).
    - **One pass:** walk the list once, tracking positives seen, negatives seen, assets found, the precision sum (AP) and the earliest rank reaching each effort threshold.
    - **Clamps:** `N = max(0, area_cells − P)` and `N_unranked = max(0, N − Nr)`, `P_unranked = max(0, P − ranked positives)`. The scanline area count and the per-cell `in_area` test can disagree on a boundary cell.
    - **AUROC:** each ranked positive scores `(Nr − negatives seen before it) + N_unranked`, where `Nr` is the ranked negatives; add `0.5 × P_unranked × N_unranked`; divide by the effective pair count `(ranked positives + P_unranked) × (Nr + N_unranked)`, so a boundary-cell disagreement can't push it above 1. Unranked positives get 0 against ranked negatives. Undefined when either effective count is 0.
    - **AP:** the sum over ranked positives of (positives so far ÷ rank) divided by P. Unranked positives add 0. Undefined when P = 0.
    - **recall@k:** assets touched in the top k ÷ `len(occupied)`, for k = P (the default, `recall_at_k`) and k = 10, 20, 50 (`recall_at`, string keys in JSON). When k exceeds the list, it's the recall of the whole list.
    - **Review effort for p in 50/80/90:** the first rank where `found × 100 ≥ p × assets` (integer comparison, so the cut-offs are exact); else `{"cells": None, "reached": share, "after": len(ranked)}`. Random baseline `ceil(p × area_cells)`, labelled approximate.
    - **Incomplete reference:** `recall_at_k`, `recall_at` and the effort values are None, with the note.
    - **Rounding:** 3 decimals for ratios; cells as integers.
  - **`score(ref, claims, chips=None)`:** unchanged output, plus `"ranking"` when chips is not None. It reuses `grid`, `occupied`, `asset_area_cells` and `area_cells`, already computed there.
  - **`from_run(run, claims, claims_block_missing=False, repo_sha=None, chips=None)`:** passes chips through.
- **`analysis/report.py:reference_of`:**
  - It passes `measure.search_candidates(run)` as the chips.
  - Failed calls are skipped. `rank_cells` orders the calls by call number (see above).
  - Every caller (`view.run_view`, `report.analyze`, `compare`) goes through `reference_of`, so all of them get it.
- **`analysis/report.py`:**
  - **`COMPARE_COLUMNS`:** gains `recall_at_k`, `auroc`, `ap`, `effort_80` (the 80% cells; None when not reached or undefined).
  - **`_meta_cols` (via `_ranking_cols`):** fills them from `reference.ranking`.
  - **`concept_rows` and `CONCEPT_COLUMNS`:** gain the four means. `CONCEPT_COLUMNS` matters because `concepts.csv` is written with `DictWriter`, which refuses unknown keys.
  - **`compare.html` concept table:** shows them.
- **Display:** `harness/web/static/adb.js` (`renderReference`), `analysis/templates/report.html` (reference section) and `frontend/src/Evaluation.tsx` (reference section); then rebuild the workspace bundle.

## Data and contracts
`GET /api/runs/{id}` → `reference.ranking`:
Illustrative values (the live numbers are recorded in the handoff, AC7):
```json
{"candidates": 31, "positives": 23, "negatives": 482776, "k": 23,
 "recall_at_k": 0.417, "recall_at": {"10": 0.25, "20": 0.417, "50": 0.417},
 "auroc": 0.71, "ap": 0.18,
 "effort": {"50": {"cells": 11}, "80": {"cells": null, "reached": 0.667, "after": 30}, "90": {...}},
 "random_effort": {"50": 241400, "80": 386240, "90": 434520},
 "notes": []}
```
An effort entry is `{"cells": N}` when reached, else `{"cells": null, "reached": share, "after": ranked cells}`. `recall_at_k`, `recall_at` and `effort` are `null` for an incomplete reference or one with no assets in the area. `candidates`, `k` and `random_effort` are always present. This is additive; existing consumers ignore it. `compare.csv` gains 4 columns at the end of the reference group, and `concepts.csv` gains 4 means.

## Decisions
### ADR-1: Where the ranking is computed
- **Options:**
  - A) inside `score()`, reusing its grid and asset cells;
  - B) a separate pass in `report.py`.
- **Decision:** A.
- **Why:** the grid, `occupied` and the area-cell count are already computed (and cached) there. B would duplicate them or need new plumbing.
- **Reversibility:** easy.
- **Sources:** analysis/reference.py:283-335.

### ADR-2: AUROC with a huge unranked tie block
- **Options:**
  - A) enumerate pairs;
  - B) closed form from the ranked positions plus a ½-credit tie block.
- **Decision:** B.
- **Why:** Pecos has 482,799 area cells; enumerating pairs is O(P × N). B is O(ranked).
- **Reversibility:** easy.
- **Sources:** the spec AC3 definition (ties count ½), which is the Mann–Whitney U form of AUROC (standard, no library).

### ADR-3: The workspace shows the ranking too
- **Context:** the spec names the run page and the static report. The workspace's reference section is now the presented interface (factory: Foundry workspace UI).
- **Decision:** add the same row there, reusing `Stat` tiles. The user approved this on 2026-11-05.
- **Why:** otherwise the metrics are invisible where people actually look.
- **Reversibility:** easy.
- **Sources:** frontend/src/Evaluation.tsx (reference section).

### ADR-4: Similarities aren't compared across calls
- **Context:** LGND similarities come from separate queries (different text or seeds, or change searches), so they aren't on one scale (spec non-goal).
- **Options:**
  - A) a global sort (simple, but mixes scales);
  - B) rank by call order only (ignores similarity);
  - C) rank within each call by similarity, then interleave the calls round-robin.
- **Decision:** C.
- **Why:** it uses each call's own ordering, and lets no single call dominate the top of the list on an incomparable scale.
- **Reversibility:** easy.
- **Sources:** tools/lgnd/results.py:37-73; the spec non-goal.

### ADR-5: `complete_within_blocks` is deferred to R2
The loader knows only complete and incomplete (analysis/reference.py:49-50). R2 adds the new class, and these metrics treat it as complete through `ref.complete`.

## Failure modes
| Failure | Detection | Behavior | Recovery |
|---|---|---|---|
| Untied run | no `tie.json` | no reference, no ranking (as today) | tie the run |
| Broken snapshot | `ReferenceError` | `reference.error`, no ranking (as today) | re-tie |
| No chips and no claims in the area | empty ranked list | AUROC 0.5, AP 0, effort not reached, note | none |
| P = 0 (no assets in the area) | count | metrics None, note "no reference assets inside the area" | none |
| Incomplete reference | `ref.complete` false | recall@k and effort None, note; AUROC/AP with note | none |
| Chip without coordinates | located requires lat/lon | never reaches ranking | none |

## Known limits
- **The per-concept `effort_80` mean** in compare averages only the runs that reached 80%. A run that never got there is left out, so check the per-run rows when the counts differ.
- **UI wording for missing values:** the classic console card and the static report show "n/a", while the workspace shows "Not defined", matching each surface's existing reference metrics. Tooltips follow each surface's convention (the classic console card has them; the workspace `Stat` tiles have none).
- **AUROC and AP for agents** are dominated by the cells the agent never ranked (on Pecos, 30 of 482,799), so they sit near 0.5 and 0. Recall@k and review effort carry the signal for agent runs.

## Security and privacy
No new inputs, endpoints or dependencies. It reads archived data already scored today.

## Performance
- **Budget:** under 0.5 s added after the first pass (spec AC8).
- **Work:** O(ranked × in_area) point-in-polygon tests (ranked is tens to hundreds of cells), plus one dict build over `occupied` cells.
- **Measured** in Verify on Pecos run `79c18997`, timing `score()` with and without chips.

## Migration and rollback
Additive. Old runs gain ranking on next view (computed from the archive). Revert the PR to remove it; nothing is stored.

## Traceability
| AC | Component | Test |
|---|---|---|
| AC1 Ranking order and dedupe | `search_candidates`, `rank_cells` | `test_order_claims_then_each_calls_results_interleaved_dedup_area_only`, `test_similarities_from_different_calls_are_not_compared`, `test_equal_similarities_keep_first_seen_order`, `test_search_candidates_are_per_call_and_skip_unscored_rows` |
| AC2 Positives | `ranking` (uses `asset_area_cells`) | covered by the AC5 fixture tests |
| AC3 Metrics | `ranking_metrics` | `test_known_answers_*`, `test_auroc_counts_the_unranked_block_as_a_half_tie`, `test_recall_at_fixed_k_and_effort_not_reached`, `test_no_assets_in_the_area` |
| AC4 Completeness | `ranking_metrics` | `test_incomplete_reference_keeps_auroc_and_ap_only` |
| AC5 Known answers | `ranking_metrics` | `test_known_answers_perfect_ranking`, `test_known_answers_ap_half_at_ranks_2_4_6`, `test_empty_ranking` |
| AC6 Shown | `from_run`, `_ranking_cols`, `concept_rows`, `adb.js`, `report.html`, `Evaluation.tsx` | `test_the_report_and_api_carry_the_ranking`, `test_compare_rows_and_concepts_carry_the_ranking`, `test_score_carries_the_ranking_only_when_chips_are_given`; browser check |
| AC7 Live | all | Pecos run `79c18997` card |
| AC8 Speed | `ranking` | timing on `79c18997` (recorded) |

## Risks and spikes
The chip-centre rule (spec assumption) may miss assets at a chip's edge. This is accepted per the spec's open question (default: centre cell only).

## Implementation plan
1. `rank_cells` and `ranking` in `analysis/reference.py`, plus unit tests (AC1–AC5).
2. Wire `score(chips)`, `from_run(chips)` and `reference_of`; add the compare columns and concept means, with tests (AC6 data).
3. Display: `adb.js`, `report.html`, `Evaluation.tsx`, then rebuild the bundle (AC6 UI).
4. Live check on `79c18997`: card values, timing (AC7, AC8); handoff.
