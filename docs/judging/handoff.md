# Judge Panel and Foundry Console — Handoff

> **Later changes (2026-11-05):** a criterion's score is now the mean of every vote over three concurrent passes, not the median ([judging stability](../judging-stability/handoff.md)); the rubric is version 3, with condition compliance and visual confirmation also measured by code ([visual check](../visual-check/handoff.md)). The [judging guide](guide.md) describes the system as it is now.

**What shipped** (branch `design/eval-harness`, 2026-11-04):
- **A scoring framework for agent-built geospatial datasets.** It has three parts:
  - a generalized rubric (`rubrics/geo-dataset-v1.yaml`) with 4 workflow criteria and 6 output criteria;
  - two criteria measured by code: claim provenance and area compliance;
  - eight criteria judged by a Bedrock panel, first of five judges (Opus 5.5, Grok 4.7, Kimi K3, DeepSeek V3.2, Mistral Large 3) and now a three-judge tribunal (Opus, DeepSeek, Kimi; see "Tribunal of three" below). A same-family judge recuses itself.
- **Aggregation** takes each criterion's median vote, then applies fatal gates (FAILED), majority failure modes, and a confidence label built from agreement and trace integrity. Krippendorff's α is computed across runs, and calibration plants defects.
- **The Team Foundry console** is a FastAPI app (T99) built on Tabler and MapLibre, with vendored assets. It has:
  - a live, plain-language trace with the raw span one click away;
  - KPIs up front;
  - Sentinel-2, USGS and NAIP basemaps showing the requested boundary, result footprints, claim pins and an imagery tile strip;
  - a scorecard showing every vote and rationale;
  - the judge panel.

  Team Foundry's name and logo are in the header and the favicon.
- **Docs:**
  - [guide](guide.md) to how a run is scored;
  - [spec](spec.md) and [design](design.md);
  - [paper notes](paper-notes.md) on the GRA paper;
  - [gap analysis](gaps.md) against the briefs;
  - the README, updated;
  - an Apache-2.0 `LICENSE`.

**Verification** (2026-11-04):
- **Static checks:** `uv run pytest` gave 122 passed. `ruff check .` and `mypy` are clean.
- [x] **AC1 Rubric.** Tested in `test_judging.py`:
  - `test_rubric_loads_and_snapshot_round_trips`;
  - `test_malformed_rubric_is_refused_naming_the_field` (6 cases: anchors, dimension, kind, unknown measured ID, calibration target, scale);
  - the sha256 is stable across a JSON round trip.
- [x] **AC2 Measured.** `test_measured_criteria_from_the_archive`, `test_provenance_is_zero_for_prose_without_claims_and_na_without_area`.
- [x] **AC3 Dossier.** `test_dossier_has_executed_work_only_and_marks_tool_output_untrusted`: no measured results, the answer appears once, and tool output is in `<tool_output>` tags.
- [x] **AC4 Panel.** `test_judge_run_writes_judgement_with_retry_failure_and_ref_filtering`, with a fake Bedrock client. It covers:
  - a retry after bad JSON;
  - a thrown error;
  - a twice-invalid reply;
  - the fallback when a model rejects `temperature`;
  - dropped refs and dropped tags;
  - cost.

  `test_same_family_judge_recuses_and_a_reserve_sits` covers recusal. Live runs listed below.
- [x] **AC5, AC6 Aggregation and gates.** `test_median_dimensions_and_majority_failure_modes`, `test_lower_median_with_four_valid_judges`, `test_fatal_gate_fails_the_run_whatever_the_judges_say`. Live: run `b2bdb4d6` (Laos, hit the token limit, no answer) scored FAILED (workflow 50, output 0, Low).
- [x] **AC7 Agreement and confidence.** `test_alpha_matches_krippendorffs_published_example` gives 0.743 / 0.815 / 0.849. Also `test_high_confidence_and_insufficient_panel` and `test_corpus_alpha_uses_whole_runs`.
- [x] **AC8 Passes.** `test_repeat_passes_report_mean_and_std`: mean 1.5 and std 0.5 over two passes; N/A with one pass.
- [x] **AC9 Calibration.**
  - Unit tests: `test_calibration_verdicts_and_exit_codes` and `test_calibrate_end_to_end_with_a_discerning_fake_panel`.
  - **Live** (`harness calibrate 6da4f34a…`, panel qwen/grok/kimi/deepseek/mistral, $0.86) passed all three: `unscoped`, `fabricated` and `no_answer`.

  | Defect | Target | Before → after | Largest other drop |
  | --- | --- | --- | --- |
  | `unscoped` | `tool_arguments` | 2 → 0 | 1 |
  | `fabricated` | `grounding` | 2 → 1 | 0 |
  | `no_answer` | `completeness` | 2 → 0 | 0 |

  The first live pass **failed** `no_answer` (2 → 2). The final reply was still visible inside the last model step, so the dossier now carries the answer once. That is the calibration catching a real bug.

  **After the Verify fixes**, the run was repeated on the concave Richardson boundary (`harness calibrate 5769706d…`, $0.73):

  | Defect | Target | Before → after | Largest other drop |
  | --- | --- | --- | --- |
  | `unscoped` | `tool_arguments` | 2 → 0 | 0 |
  | `fabricated` | `grounding` | 2 → 0 | 1 |
  | `no_answer` | `completeness` | 2 → 0 | 2 (flagged non-specific: removing the answer also sinks honest uncertainty, which is expected) |

  The fabricated site is now found by a grid search inside the polygon. The run exited 0.
- [x] **AC10, AC12–AC14 Console.**
  - Tests in `test_web.py`:
    - `test_pages_assets_and_archive_endpoints_render_offline`: every asset is vendored and there are no CDN URLs;
    - `test_run_view_kpis_map_and_scorecard`;
    - `test_scripted_run_streams_steps_then_the_full_view`: a real agent subprocess, an SSE stream, then `done` with the full view.
  - Headless Chromium screenshots of a judged Richardson run and the console home were reviewed for layout.
  - **Live:** console run `5769706d` (Sonnet, Richardson city limits) streamed 8 steps and 51 chips. The judges then streamed one by one, ending at score **100**, High confidence:
    - 6/6 claims verified;
    - 5/5 claims in the area, with a search footprint of 51/51;
    - agent $0.18, judging $0.15.
- [x] **AC11 Plain-language trace.** `test_timeline_sentences_are_plain_english` and `test_live_span_event_carries_entry_and_chips`.
- [x] **AC15 Layering and docs.** `test_layers.py` covers the new modules (`analysis` may import `tools.describe` and `tools.*.describe`), plus the `judge/system` prompt file. The docs are listed above.

**Live judging so far** (all with `judging.auto` or `harness judge`):

| Run | Agent | Task | Score | Confidence | Judging $ |
| --- | --- | --- | --- | --- | --- |
| `5769706d` | Sonnet | Richardson data centers (console) | 100 (re-judged after the hash fix: 100) | High | 0.15 / 0.14 |
| `8a12c6ba` | Sonnet | Dallas 50 km data centers | 100 (re-judged; the first judgement had a false `no_tool_data` gate from a status-name bug) | High | 0.12 |
| `8a6e054b` | Kimi | Dallas data centers | 87.5 (workflow 75) | Medium | 0.38 |
| `ade80a36` | Sonnet | ZIP 75080 data centers | 90 (output 80) | High | 0.20 |
| `c9edb642` | Sonnet | Khammouane farmland | 88.8 | High | 0.20 |
| `b2bdb4d6` | Kimi | Laos farmland (token limit, no answer) | FAILED (workflow 50) | Low | 0.46 |
| `daa193db` | Kimi **on AgentCore** (`harness run --backend agentcore`, auto-judged) | `dallas-dc-strict` | 100 (MAD 0.13; Opus voted 1 on 3 criteria) | High | 0.26 |

On `daa193db`, Kimi was the agent, so Kimi recused and Opus sat. `harness check` reported 0 missing fields and 16/16 claims matched.

**Infrastructure failures are not scored** (2026-11-04, after run `25b41808`): that Kimi run started on expired credentials, made no model call, and the panel scored it FAILED 0 for $0.06. Runs whose model calls all failed now skip the panel and show **not scored** with the cause (test `test_infrastructure_failure_is_not_scored_and_replaces_a_stale_judgement`; 124 tests pass). Its re-run, `53fd4e2a` (Kimi, ZIP 75080), scored **95.8**, High: workflow 100, output 91.7, 10/10 claims verified and inside the ZIP. Result relevance got a median of 1: imagery checks confirmed none of the ten candidates, and 3 of 5 judges flagged overconfidence.

**Tribunal of three** (2026-11-04, the user's call): the panel is now Opus 5.5, DeepSeek V3.2 and Mistral Large 3, with reserves Kimi K3, Qwen3 235B and Sonnet 5.5. The judges dropped were chosen from per-judge stats over the 7 runs judged by the five-judge panel:

| Judge | Avg latency | Avg cost | Errors | Mean bias vs. peers' median |
| --- | --- | --- | --- | --- |
| Grok | **143 s** | $0.083 | **1** | −0.13 |
| Kimi | 50 s | $0.086 | 0 | −0.09 (also an agent: recuses on Kimi runs) |
| Qwen | 11 s | $0.004 | 0 | **+0.25** (most lenient) |
| Opus | 30 s | $0.246 | 0 | −0.50 (strictest, 3 runs) |
| DeepSeek | 13 s | $0.009 | 0 | +0.13 |
| Mistral | 18 s | $0.012 | 0 | +0.14 |

Grok is out, Kimi and Qwen are reserves. A reserve now also **stands in** for a judge that fails, so every pass keeps three votes (tests `test_tribunal_seats_three_and_a_reserve_stands_in_for_a_failed_judge`, `test_a_tribunal_short_a_vote_is_not_scored_by_two`). Confidence is now relative to the seats: one seat short is Medium, two short is Low. Archived five-judge judgements keep their labels. Judging cost per pass drops from about $0.38 to $0.16–0.19. **Live:** console run `3d7ac12a` (Sonnet, ZIP 75080) seated Kimi for Opus, then DeepSeek and Mistral. It scored 100, High (Kimi 87.5, DeepSeek 100, Mistral 100), with judging at $0.10 and the slowest verdict at 15 s, down from Grok's 85–140 s.

**Mistral swapped for Kimi** (2026-11-04, the user's call): the tribunal is Opus, DeepSeek and Kimi, and the reserves are Mistral, Qwen, then Sonnet. Kimi judges and also runs as an agent; on a Kimi run it recuses and Mistral sits, as Mistral does for Opus on Sonnet runs. That leaves the two most lenient judges (Mistral +0.14, Qwen +0.25) on the bench, and seats the judge closest to its peers (Kimi −0.09). **Live:** `harness judge 3d7ac12a` (Sonnet) seated Mistral for Opus, then DeepSeek and Kimi, and scored 100, High (votes 100 / 100 / 93.8), with judging at $0.09. Kimi took 128 s that time, against 15 s on the earlier pass, so Kimi can now be the slow seat.

**Wrong area, step limit** (2026-11-04, run `c251934d`, Kimi, "signs of forest fires in nothern california"): the area lookup took Nominatim's first hit for "Northern California", a 20 m building in San Francisco (OSM way 257960526). Enforcement then fenced every LGND search into it, every search came back empty, and Kimi spent the 40-step limit working around that: no answer, FAILED, $1.21. Two fixes:
- **Lookup** (`harness/area.py`): a city, region, country or postal code must match a boundary or a named place (`category` boundary/place, `place_rank` ≤ 27), taken from the first 5 hits. Otherwise the run goes ahead with no area check, and the console says why. "Northern California" has no official boundary, so it now gets no check; "California" still resolves to relation 165475.
- **Enforcement** (`agent/hooks.py`): a narrower area that the agent sends inside the boundary (circle, bbox or ring, every outline point inside) is kept. Only an area that reaches outside, or no area at all, is replaced. The agent prompt says so. This is agent-side, so the AgentCore runtime needs a redeploy to pick it up.

Re-run `821bd88f` on the same prompt: 5 model calls, 7 tool calls, 38/38 claims verified, **87.5 High** (Opus 75, DeepSeek 87.5, Mistral 87.5 for Kimi), agent $0.49, judging $0.13. Tests: `test_a_building_named_after_a_region_is_not_the_region`, `test_a_narrower_area_inside_the_boundary_is_kept`; 129 pass.

**Agreement across runs:** `harness agreement --all` gives Krippendorff's α (ordinal) = **0.502**, 95% CI 0.12–0.67, over 7 judged runs, 56 run × criterion units and 6 distinct judges. That is moderate agreement, close to the paper's α ≈ 0.56 among human experts. Two things widen the CI:
- most votes are 2, a ceiling effect that depresses α;
- there are only 7 runs.

More runs, and runs that are actually weaker, will tighten it.

**Verify review** (independent subagent): 115 tests passed and ruff and mypy were clean before its findings. It found 4 bugs, all fixed with regression tests:
1. within-one was averaged after the spread, not per pass;
2. the fabricated site could fall outside a concave area;
3. the unscoped relabel missed trimmed outputs and `area` keys;
4. a no-op perturbation was still judged.

Minors were fixed too: claim-to-area matching by position, the scale max, no dimension scores when no judge is valid, dropped passes left out of α, and the design text on `gated`. It rated the console's JS behavior (map clicks, toggles) as PARTIAL, because only the JSON shapes are tested; the headless screenshots are the evidence for the rendering.

**Deploy:** no AgentCore redeploy was needed. `git diff a68daf2 -- agent/ infra/ Dockerfile`, the tool clients and `prompts/agent/` are all empty. Judging and the console run in the harness, on the operator's machine, against the archive. The live AgentCore run `daa193db` above used the deployed runtime unchanged.

**Decisions made in this pass [team]:**
- **The panel** is a tribunal of Opus (chair), DeepSeek and Kimi, with reserves Mistral, Qwen, then Sonnet (revised from five judges; see above). Sonnet is a reserve only, because it's the default agent and shares Opus's family.
- **Recusal is on** (`recuse_same_family: true`). On Sonnet runs, Opus sits out and Mistral takes its seat; on Kimi runs, Kimi sits out and Mistral takes its seat. If you want Opus on every run, set it to false, and the panel then has a same-family judge. **This is the call most worth a second look.**
- **Per-run α is not shown** (design review pass 1). Agreement per run is within-one and MAD; α is reported across runs.
- **Judges never see the measured results**, so code and LLMs give two independent lines of evidence.

**Specialists consulted:** ML/AI and AI Safety (judge design, injection boundary), QA Automation, Product Designer and Frontend (Tabler/MapLibre, dataviz palette check), and Technical Writer.

**Gate history:**
- **Design:** 3 subagent passes, with 5 → 3 → 0 blockers.
- **Build:** self-checks after each slice.
- **Verify:** this record, plus an independent verify review (findings handled above).

**Follow-ups** (ordered; see [gaps.md](gaps.md)):
1. An answer key for outcome correctness: switch the task to solar or wind sites against USPVDB/GRW (V96), and add a measured recall/precision criterion.
2. Human-expert ratings of 20 runs, to validate the panel the way the paper did (expert α ≈ 0.56).
3. ADB's rubric, when it arrives: drop it in as YAML, with a `calibration` map.
4. Judging cost rises with dossier size: the Laos run cost $0.46. Consider tighter `tool_result_chars` on very long tool tables.
5. ~~Grok 4.7 is the slowest judge (70–125 s).~~ Resolved 2026-11-04: Grok left the panel when it became the three-judge tribunal (see above). The panel still waits for every seat, so the slowest seated judge (now Kimi at times) sets the time to a score.

**Risks:**
- Absolute scores depend on the panel's strictness (GRA §6). Compare runs judged by the same seats and rubric sha.
- LLM judges can share blind spots on the same dossier. Calibration bounds this but doesn't remove it.
