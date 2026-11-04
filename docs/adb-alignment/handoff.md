# ADB Alignment: Handoff

**What shipped:**
- **A summary of the LGND/Ode inception report** as it bears on Track 1 ([lgnd-ode-brief.md](lgnd-ode-brief.md)). It's paraphrased, the report itself isn't in the repo, and it ends with a gap table.
- **Fixes for four of those gaps:**
  - **reference sets**, scored with the benchmark's unit, matching rule and metrics;
  - **data and licences per run**, with a "presentable" verdict;
  - **per-concept and transfer reporting** in `compare`;
  - **a T1 suite** over the benchmark's concepts and places, plus a first, licence-clean reference set (USGS USPVDB, Pecos County, TX).

**The headline result (live run `f5a55164`, Pecos County solar):**
- **The judges scored it 100/100, High confidence,** and all 5 claims were verified against the tool output.
- **Against the reference, the agent found 4 of the county's 12 facilities:** site recall 0.333, cell precision 1.0, count ratio 0.333, lift 169.
- **So the agent's work was clean and honest, but incomplete.** Only a reference check can show that, and it's the gap the benchmark exists to measure.

**Verification**
- [x] **AC1: format and loader.** Tests: `test_loader_refuses_missing_or_non_commercial_licences`, `test_licence_filter_matches_whole_tokens_only` (LGND ids pass; NC, ND, NoDerivatives, NonCommercial and academic are refused) and `test_the_shipped_pecos_set_loads_and_is_licence_clean`.
- [x] **AC2: matching and metrics.** Tests:
  - `test_any_touch_matching_recall_precision_count_ratio_and_lift`;
  - `test_a_polygon_asset_is_found_by_any_flagged_cell_it_touches_and_counts_once`;
  - `test_neighbouring_flagged_cells_merge_into_one_site`;
  - `test_incomplete_reference_reports_precision_only`;
  - `test_no_claims_means_recall_zero_and_precision_undefined`.

  On real data, each facility's own coordinate gives recall, precision and count ratio of 1.0, over 482,799 area cells. Scoring takes 0.2 s after a first pass of about 2.6 s, once the code was rewritten to scanline plus edge-walk.
- [x] **AC3: ties, as snapshots.** Tests: `test_tie_snapshots_the_set_and_scoring_reads_only_the_archive` (a rebuilt set doesn't change archived metrics; `stale` is flagged), `test_an_untied_run_has_no_reference_and_a_broken_snapshot_reports_an_error` and `test_tie_refuses_a_bad_set_and_a_bad_id`.
  - **Live:** `harness run --reference` tied before the run. `harness reference tie` and `list` worked; an unknown id gives a clear error.
- [x] **AC4: console, report and API.**
  - **Live, console on port 8788:** the run page shows the "Against the reference" card, and the map layers `ref-assets-fill`, `ref-assets-line` and `ref-false` are present, with no console errors.
  - **Static report:** both sections present.
  - **API:** `GET /api/runs/{id}` returns `reference` and `licences`.
  - **The browser probe** (`tests/browser/console_probe.py`) passes on the run. The score is unchanged.
- [x] **AC5: the first real set.** `references/uspvdb-tx-pecos-v4/`: 12 facilities from USPVDB v4.0 (2026-04-14), with the area from the TIGER county boundary (GEOID 48371). It was built by `harness reference build-uspvdb …` (see its `BUILD.md`), and the builder has a test with fixture bytes. The live run is above.
- [x] **AC6, AC7: data and licences.** Tests: `test_licences_list_sources_and_mark_lgnd_unknown`, `test_roda_licence_is_read_from_the_archived_tool_result` and `test_lgnd_tools_without_an_index_fold_into_the_service_and_model_roles_merge`.
  - **Live:** NAIP, OSM, the models and the reference are all presentable. The LGND Geo service is unknown, so the run reads **"check before sharing"**.
  - Two defects the live run exposed were fixed: an LGND tool listed as "dataset unknown", and a duplicated model.
- [x] **AC8: suite metadata.** Test: `test_suite_entries_with_metadata_are_stored_and_tied` (`suite_meta` stored; tied before the run; plain entries unchanged). `suites/adb-t1-v1.yaml` has 7 T1 prompts on one model, within `max_runs_per_suite`, and **wasn't run**, per the spec.
- [x] **AC9: per concept and transfer.** Test: `test_concept_and_transfer_rows_pool_each_role_and_skip_nulls`, plus `concepts.csv` and the `compare.html` sections. Not exercised on a real suite, because none has been run.
- [x] **AC10: docs.** The developer guide (CLI, suite format), the judging guide, gaps, the factory, the docs index and `references/README.md`; `tests/test_docs.py` passes.

The full suite, ruff, the formatter, mypy and the infrastructure tests all pass.

**Exercised live:**
- AgentCore run `f5a55164-3752-4309-94df-9a2023b1d2dc`: Sonnet, $0.16 agent plus $0.07 judging;
- the console on 8788, with screenshots and the probe;
- the static report;
- the USPVDB and TIGERweb downloads.

**Gate history:**
- **Define:** self-review.
- **Design:** three subagent passes.
  - **Pass 1:** 10 blockers. The main ones:
    - scoring now reads a snapshot in the archive;
    - ties are written before the run;
    - the area comes from TIGER, not OSM (no ODbL in the repo);
    - analysis/harness layering;
    - the CSV columns;
    - lift computed over one cell population;
    - the token-based licence filter;
    - transfer aggregation defined.
  - **Pass 2:** 7 issues. Four were inconsistencies in the documents, from the reviewer reading code mid-rewrite. The real ones were the mixed cell populations, the ND and NC spellings, and the area's provenance. USPVDB's licence is no longer called a "U.S. Government work", because it's co-produced with LBNL.
  - **Pass 3:** 10 edge-case definitions, brought to Miguel with proposed rulings, which he accepted. They're recorded in the design under "Rulings on the last review pass".

**Decisions and deviations**
- **Reference metrics sit beside the score;** the rubric is untouched. That keeps scores comparable and avoids colliding with PR #7's rubric bump.
- **Asset cells use an interior scanline plus an edge walk** sampled at 1/16 of a cell, replacing an exact per-cell test, for speed: 5 s became 0.2 s. A cell clipped by less than 10 m at a corner could be missed. That's documented.
- **During verification I tied an unrelated archived run** (`7b3d00f8`, Jodhpur) to the Pecos set, to exercise `reference tie`. I removed the snapshot and rebuilt its report, so it's back to how it was.

**Follow-ups**
- **Ask LGND** for its terms of service, so runs can be "presentable", and for its prepared **Nagoya warehouse and tank** and **Manila bridge** reference sets, plus the benchmark's grid origin.
- **Run `suites/adb-t1-v1.yaml`** (7 runs, about $5) to get per-concept and transfer numbers.
- **Measure the requested period:** that belongs to the prompt-compliance work in PR #7.
- **Pair transfer gaps by place** once a concept has several home places.

**Risks to watch**
- **Reference completeness is the source's claim.** USPVDB says it misses facilities outside EIA-860, so recall can be understated.
- **The boundary differs from the run's:** the reference area is TIGER and the run's enforced area is OSM. Claims in edge slivers are counted as outside the area, not scored.
