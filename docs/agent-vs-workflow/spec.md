# Agent vs Workflow — Spec

**Roadmap:** R5 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R3 (seeds recorded per run), R4 (ranking metrics). A complete reference: Pecos today, R1 or R2 for ADB places.
**Size:** M–L (about 4–5 days)

## Problem
The report asks a question it calls exploratory: does an off-the-shelf agent harness with the LGND MCP connector reproduce the performance of the defined workflow it would be driving (§5.8, Table 1) **[ext]**? Our harness runs the agent half. Nothing runs the workflow half on the same inputs. So when the Pecos agent run finds 4 of 12 solar farms (docs/adb-alignment/handoff.md), we can't say whether that is the agent's shortfall or the tools' ceiling. LGND, Ode and ADB can't tell whether to trust an agent to drive the workflow, or what it costs them to do so.

## Users
- **LGND/Ode,** who own the §5.8 question and will report its pitfalls **[ext]** (primary).
- **Evaluators** deciding whether an agent's low recall is the agent's fault or the tools'.

## Goals
- For an agent run, the harness can run LGND's classifier workflow on the same seeds, index, area and reference. It reports the agent's gap in recall, ranking quality, review effort, cost and steps.
- The gap is reproducible: the workflow run is archived like any run and replays offline.

## Non-goals
- **Reproducing the report's numbers.** Its workflows are AEF, Clay and FarSLIP embeddings with linear classifiers on 160 m cells, trained on many labels (Table 1, Table 9, Table 19) **[ext]**. Ours is LGND's hosted classifier on 2–3 seeds.
- **Improving the agent** or its prompt to close the gap. The report says the agentic test involves no agent development (Table 1) **[ext]**.
- **A `like`-search workflow variant** (Table 9, few-shot **[ext]**). It's a candidate follow-up.
- **Judging workflow runs.** There's no answer and no reasoning to score, so the panel isn't called.
- **Deleting LGND classifiers.** The MCP tool list has no delete tool (tools/lgnd/descriptors.py:13-32).

## User stories
- As LGND, I want the agent's recall@k beside the workflow's on the same seeds and reference, so that I can answer §5.8 with numbers.
- As an evaluator, I want to see which steps the workflow takes that the agent skipped, so that I can tell planning failures from tool limits.

## Acceptance criteria
- [ ] **AC1 Command.** `uv run harness workflow run --pair <agent-run-id>` makes a paired workflow run. It copies, from the agent run: its seeds (R3 manifest `seeds`), its reference tie, and its index (the LGND `scope.index` the agent used most, by call count; on a tie, `s2`). It refuses an agent run without seeds or without a reference tie, and names the missing one. A suite entry with `pair_workflow: true` does the same after each agent run. The run-count guard (harness/cli.py:249-265) counts paired runs.
- [ ] **AC2 Recipe** (fixed, recorded in the manifest `workflow` block):
  1. `search_chip_lat_lon` on each seed → positive nodes.
  2. `search_chip_lat_lon` on 10 points drawn uniformly inside the reference area with RNG seed 46 → negative nodes. A negative whose cell touches a reference asset is replaced by the next draw.
  3. `toolbox_classifier_build` named `team46-wf-<run id prefix>`, with examples `{<concept>: positives, other: negatives}`.
  4. `toolbox_classifier_apply` with that classifier and `scope.area` set to the reference area as a ring (simplified to fit LGND's limits; the simplification is recorded).
- [ ] **AC3 Archived as a run.** The workflow run has `backend: workflow`, no model, and every LGND call as a tool span in the same form as agent spans. So `located_results` (analysis/judging/measure.py:93-117) and the reference scoring read it unchanged. Its score is null, with the cause "workflow run: not judged". It's tied to the same reference snapshot as its pair, and it replays with no network.
- [ ] **AC4 Flagged and ranked.** The workflow's claims are the apply results labelled with the concept. Its ranking (R4) orders those results by descending `margin`, then the rest by ascending margin. `margin` is kept on parsed results; today it is dropped (tools/lgnd/results.py:70).
- [ ] **AC5 The gap.** The agent run page and `harness compare` show an **Agent vs workflow** table per pair, plus a `pairs.csv`. Columns: site recall, recall@k, AP, review effort to 80%, cost (USD, agent model cost; LGND calls unpriced and labelled so), tool calls, runtime (s), and for each **gap = workflow − agent**. Review effort's gap is agent − workflow, so positive always means the agent did worse. A final row gives the mean gap over all pairs.
- [ ] **AC6 Failure is reported, not hidden.** If any recipe step errors, the workflow run's status is `error` with LGND's message, and the pair row reads "workflow failed: <step>". No gap is computed.
- [ ] **AC7 Live proof.** The 3-seed Pecos runs from R3's suite (`suites/adb-t1-seeds-v1.yaml`) are each paired. The handoff records the table. If R1 has shipped, one 2-seed Gifu warehouse pair on `s2` is also run.
- [ ] **AC8 Tests.** On recorded LGND outputs for steps 1–4, a test checks that the workflow run's metrics are deterministic, that the negative replacement rule holds, and the sign convention of every gap column.

## Success signals
- **Metric (§5.8 reproduction rate):** numerator = pairs where the agent's recall@k is at least 90% of the workflow's; denominator = pairs where both are non-null. It's reported with no target, because it is the finding.
- **Metric (pair completion):** numerator = pairs with a computed gap; denominator = pairs attempted. Target ≥ 90%. Below that, the workflow recipe, not the agent, is what we're measuring.

## Constraints
- **Report framing:** the agentic test is exploratory, outside the core deliverables, and its results are report-only (§5.8, Table 1) **[ext]**. The output is a table and a handoff, not a score change.
- **Licences:** LGND's terms of service are unknown (docs/adb-alignment/handoff.md, Follow-ups). So workflow runs, like agent runs, read "check before sharing" (analysis/licences.py:55).
- **Cost:** no Bedrock spend for workflow runs. Each makes about 14 LGND calls (3 seeds, 10 negatives, build and apply). Any LGND rate limit is unknown, so Design probes it.
- **Account state:** each build leaves a classifier in the team's LGND account (`toolbox_classifier_list`). Names carry the run id, so they can be traced.

## What exists today
- The LGND tool list includes `toolbox_classifier_build`, `_apply`, `_list` and `_get`: tools/lgnd/descriptors.py:25-28. Apply reads `area` unless `nodes` or `inside` is given: tools/lgnd/descriptors.py:44-48.
- Apply results are parsed as rows with lat, lon, bbox, label, margin and fit, but `margin` isn't kept: tools/lgnd/results.py:42, 68-73. The build is summarised from `examples` and labels: tools/lgnd/describe.py:66-71.
- An MCP client with refreshing LGND auth, usable outside the agent: tools/lgnd/client.py:11-20.
- Backends are `agentcore` and `local` only: harness/invoke.py:86-94.
- Cost, tokens, tool calls and runtime per run: analysis/signals.py:18-24, 64-70; compare columns: analysis/report.py:118-124.
- The reference tie and scoring from the snapshot: harness/reference.py:48-63; analysis/reference.py:343-374.

## Assumptions and open questions
- **Assumption:** `toolbox_classifier_build` takes examples as a label → nodes map (tools/lgnd/describe.py:67). If the schema differs, Design adapts step 3. The recipe's intent stays the same.
- **Assumption:** apply over a county-sized ring returns every result, not a capped page. If it's capped, the recipe tiles the area and the manifest records the tiles.
- **Open:** which embedding model backs LGND's classifier on each index? — owner: Miguel (asks LGND); default: record "LGND-hosted, model unstated" in the manifest.
- **Open:** are 10 random negatives right, or does LGND expect positives only? — owner: team (Design probe); default: 10 negatives, as in AC2.
- **Open:** should the workflow also run at the report's larger label budgets (for example 120 labels, Appendix B **[ext]**), using reference assets as labels? — owner: team, with LGND; default: no, equal seeds only. It would need held-out assets, and that's a follow-up.
