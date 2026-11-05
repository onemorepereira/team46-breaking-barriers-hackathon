# Handoff: ranking metrics (R4)

Date: 2026-11-05. [Spec](spec.md) · [design](design.md).

## What shipped
Every run tied to a reference now shows how well its search ranked the real assets, not only which sites its answer reported:
- recall@k, with k = the number of asset cells (the benchmark's convention), plus k = 10, 20 and 50;
- AUROC and AP;
- review effort: cells an analyst inspects, in this run's order, to find 50/80/90% of the assets, beside the random-order baseline.

**How the ranking is built** (`analysis/reference.py`):
- the answer's sites come first, in answer order;
- then each LGND search call's results, ordered by that call's own similarity;
- the calls are interleaved round-robin in the order they were made (call number);
- the list is deduplicated by 160 m cell, area cells only.

**Which results count:** only search results (rows with a similarity) are candidates. Survey grid cells and classifier rows are not. They come straight from each call's tool result (`measure.search_candidates`), so a place two searches returned keeps its rank in each.

**AUROC with unranked cells:** the cells the agent never ranked are tied at the bottom, so AUROC uses a closed form with ½-credit ties and effective counts. Review effort uses an exact integer cut-off.

**Where it shows:**
- `GET /api/runs/{id}` → `reference.ranking`;
- the classic console's reference card;
- the static report;
- the workspace's "Independent reference benchmark" section (approved by the user);
- `harness compare` (`recall_at_k`, `auroc`, `ap`, `effort_80` per run; means per concept).

## Proof (2026-11-05)
| AC | Proof |
|---|---|
| AC1 Ranking | `tests/test_ranking.py`: `test_order_claims_then_each_calls_results_interleaved_dedup_area_only`, `test_similarities_from_different_calls_are_not_compared`, `test_equal_similarities_keep_first_seen_order`, `test_calls_are_interleaved_in_the_order_they_were_made_not_completed`, `test_search_candidates_are_per_call_and_skip_unscored_rows` |
| AC2 Positives | the AC5 fixture tests and `test_score_carries_the_ranking_only_when_chips_are_given` (area cells touched by an asset) |
| AC3 Metrics | `test_known_answers_*`, `test_auroc_counts_the_unranked_block_as_a_half_tie`, `test_recall_at_fixed_k_and_effort_not_reached`, `test_no_assets_in_the_area` |
| AC4 Completeness | `test_incomplete_reference_keeps_auroc_and_ap_only` |
| AC5 Known answers | perfect ranking: AUROC 1.0, AP 1.0, effort 80% = 3; ranks 2/4/6: AP 0.5; empty: AUROC 0.5, AP 0, not reached |
| AC6 Shown | `test_the_report_and_api_carry_the_ranking` (`report.analyze` and `run_view`), `test_compare_rows_and_concepts_carry_the_ranking`. In the browser at 1440 and 375 px, the classic console card and the workspace section both show the Ranking row, with no horizontal scroll and no console errors. `harness replay 79c18997` writes the static report with the Ranking tiles |
| AC7 Live | Pecos run `79c18997` (below) |
| AC8 Speed | Pecos, 482,799 area cells: ranking adds +0.03 s over the claim-only score after the first pass (budget 0.5 s) |

**Live: Pecos run `79c18997`** (Sonnet on AgentCore, tied to `uspvdb-tx-pecos-v4`):

| Metric | Value |
|---|---|
| Site recall (the answer's 5 sites) | 0.417 (5 of 12 farms) |
| Ranked cells | 30 (one search call) |
| **Recall@k** (k = 2,856 asset cells) | **0.667** (8 of 12 farms) |
| Recall@10 / @20 / @50 | 0.417 / 0.667 / 0.667 |
| **Cells to 50% of farms** | **11** (random ≈ 241,400) |
| Cells to 80% / 90% | not reached (67% after 30 cells) |
| AUROC / AP | 0.505 / 0.011 |

**Diagnostic signal (spec):** this run's recall@k (0.667) beats its site recall (0.417). Its search found 3 farms its answer left out, which the claim-only metrics can't show (1 of 1 qualifying runs).

**Checks:**
- `uv run pytest` passes;
- `ruff`, `ruff format` and `mypy` are clean;
- frontend: `tsc`, `npm test` (20/20) and the build.

## Gates
**Design:** 3 independent passes.
- **Pass 1 (3 blockers):**
  - survey and classifier rows were being ranked;
  - `CONCEPT_COLUMNS` was missing the new keys;
  - similarities were compared across calls.
- **Pass 2 (2 blockers):** the design contradicted itself on candidates, and located results' cross-call dedupe distorted per-call ranks.
- **Pass 3 (1 blocker):** call order was result order, not the order calls were made. Fixed with the user's OK.

The spec's AC1 is amended to match.

**Verify:** an independent review found no blocking issues.
- **Maths:** checked against a brute-force version in 3,000 random trials (ties, the unranked block, P = 0, N = 0, short rankings, multi-cell assets), with 0 mismatches.
- **Bundle:** a fresh build reproduces the committed workspace bundle exactly.
- **Its non-blocking findings, fixed:**
  - the random baseline now shows on "not reached" effort too (console and workspace);
  - a search call with no call number gets its own group instead of merging (`test_calls_without_a_number_stay_separate_groups`);
  - cells outside the area are tested once;
  - untied runs skip parsing candidates;
  - a note explains a null AUROC when every area cell is an asset;
  - spec AC1's opening sentence now matches the code.
- **Speed at scale** (the reviewer's timing): about 0.17 s at 3,000 candidates and 1.8 s at 30,000. Real runs so far have tens.

## Known limits
- **AUROC and AP for agents** are dominated by the cells the agent never ranked (30 of 482,799 on Pecos), so they sit near 0.5 and 0. Recall@k and review effort carry the signal.
- **The per-concept `effort_80` mean** averages only the runs that reached 80%.
- **Chips are scored at their centre cell** (spec open question, default kept).
- **`complete_within_blocks`** references (R2) will count as complete once R2 adds them.

## Launch
- **Ships with the PR.** The console and `harness replay` compute the ranking when a run is viewed. There's no migration, nothing is stored, and no AgentCore redeploy is needed: the agent is unchanged.
- **Monitor:** a run whose reference card shows "Not defined" for every ranking metric on a complete reference means no candidates fell inside the area, and the note says so.

## Rollback
Revert the PR. Nothing is stored; the ranking is computed from each run's archive when it's viewed.
