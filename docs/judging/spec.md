# Judge Panel and Foundry Console — Spec

**Track:** Standard   **Product stage:** Introduction
**Status:** Building   **Last updated:** 2026-11-04

> References like (T116) or (V53) are lines in the [Technical](../Clay-Foundry-Technical-Hackathon.md) and [Vision](../Clay-Foundry-Vision-Hackathon.md) briefs. **[GRA §x]** cites the Geospatial Research Agent paper (arXiv 2610.15750), summarized in [paper-notes.md](paper-notes.md). **[team]** marks our own decisions.

## Problem

ADB needs to know whether it can trust a dataset an agent built. Today our harness records every decision and checks that claims match tool output verbatim, but it doesn't score the run (V110, V123). The briefs ask for a score on two dimensions: workflow signals from the trace, and output quality against a rubric (T116–T118). ADB hasn't supplied a rubric (V191), so the score has to come from a rubric that generalizes across geospatial dataset-build tasks, applied by judges whose verdicts can be checked **[team]**.

## Users

- **ADB analysts and Clay's data team** (V26, V27) decide whether to trust a run's dataset. They need one score, what it rests on, and how sure the judges are.
- **Harness developers** (V28) need to see which criterion failed and on which step.
- **Hackathon judges** need to see the loop working, in a page that reads at a glance **[team]**.

## Goals

- Every run gets a score: per criterion, per dimension (workflow, output) and overall.
- The score is produced by a panel of five LLM judges from five model families. With an odd panel, the median is always one judge's actual vote, so there are no ties **[team]**.
- Each score says how confident it is: how far the judges agree, and whether the deterministic checks pass.
- Judges can be tested. Planted defects must lower the criterion they target.
- The console shows the run in plain language, with the map, tiles, score, cost and counts up front.

## Non-goals

- ADB's own rubric. The rubric is a YAML file. When ADB sends theirs, it replaces ours with no code change.
- Human expert ratings. We report judge-to-judge agreement (as the paper does with experts [GRA §4.1.4]) and leave human calibration as a follow-up.
- Caption generation (Track 2).
- Authentication or multi-user hosting. The console binds to 127.0.0.1.

## User stories

- As an ADB analyst, I open a run and see its score, its confidence, and why each criterion got its score, with links to the steps that justify it.
- As a harness developer, I see each step in plain English ("Searched LGND's NAIP imagery for *data center* inside Richardson, TX: 24 matches"). One click shows the raw span.
- As a reviewer, I see every result on a satellite map, inside or outside the requested area, and I can click a result to see its tile and its evidence.
- As the team, I swap a judge or the rubric in `harness.yaml` and re-judge an archived run without re-running the agent.

## Acceptance criteria

- [ ] **AC1 Rubric file.** The rubric lives in `rubrics/*.yaml`. Each criterion has an ID, a dimension (`workflow` or `output`), a kind (`judged` or `measured`), a question, and, for judged criteria, anchored definitions for 0, 1 and 2. A malformed rubric is refused with a message naming the bad field. The rubric is snapshotted into the judgement, so replay uses the rubric the run was judged with.
- [ ] **AC2 Measured criteria.** Two criteria are computed by code from the archive, with no LLM:
  - **claim provenance**: the share of declared claims whose value is found in the cited tool result. It is 0 when the claims block is missing, or when it is empty but the answer has text;
  - **area compliance**: the share of coordinate claims (the dataset's locations) inside the requested area. It is N/A when the prompt names no area or the answer has no coordinates. The share of LGND results inside the area is shown alongside, on the map and KPIs, as **search footprint**. It isn't scored, because the harness enforces the boundary on searches.

  Both are replayable from the archive alone.
- [ ] **AC3 Evidence dossier.** Judges see a dossier built by code from the archive: the task, the search area, the tools available, every step in order (reasoning, tool calls with arguments, tool results with their `[ref Tn]` labels, truncated to a stated cap), the final answer, and each step's usage (tokens, latency) with run totals (steps, tokens, cost). Judges do not see the measured results, so their scores don't double-count them. Tool output is marked as untrusted data. Only executed work counts: the dossier contains nothing the agent didn't do [GRA §3].
- [ ] **AC4 Panel.** `harness judge <run_id>` sends the dossier to five judges in parallel and writes `runs/<id>/judgement.json` to the archive. Each judge returns, for every judged criterion, a score (0, 1 or 2), the step references it relied on, and a rationale. It also returns failure-mode tags from a fixed list.
  - If a judge shares a model family with the agent under test, it recuses itself and a reserve judge takes its place (self-preference [GRA §6]).
  - A judge reply that isn't valid JSON is retried once. If it is still invalid, the judge is recorded as failed. Fewer than three valid judges means the run is not scored.
  - References to steps that don't exist are dropped and counted.
- [ ] **AC5 Aggregation.** For each judged criterion, the panel score is the median of the valid judges. With an even count, it's the lower median, which is conservative and keeps the score an actual vote. A criterion's 0–100 score is the median ÷ 2 × 100, and a measured criterion's is its share × 100. A dimension's score is the mean of its criteria (N/A excluded); the overall score is the mean of the two dimensions. A failure mode is reported when a majority of valid judges tag it.
- [ ] **AC6 Fatal gates.** Following the paper's automatic fails [GRA A.3.1], these runs score 0 overall and on every output criterion, whatever the judges said:
  - a run with no final answer;
  - a run with no successful tool call.

  The workflow scores are still shown for diagnosis. The page shows **FAILED** with the gate's reason.
- [ ] **AC7 Agreement and confidence.** Each judgement reports:
  - per-criterion spread (max − min) and unanimity;
  - **within-one**: the share of criteria where all judges are within one point of each other;
  - **MAD**: mean absolute deviation of votes from the median.

  Across a suite (or any set of judged runs), Krippendorff's α (ordinal) is computed with judges as coders and run × criterion as units. It must match the reference implementation to 3 decimals on Krippendorff's published example. α is not shown per run, because 8 units are too few for a stable value.

  **Deterministic checks pass** when trace integrity holds (0 missing fields, 0 archive errors) and no fatal gate fired.

  With N passes:
  - the headline score uses the mean of the pass medians;
  - within-one is averaged across passes;
  - "5 valid judges" must hold in every pass, with no pass dropped, for High. The Low rule uses the minimum count across passes;
  - failure modes take a majority of all votes pooled across passes;
  - corpus α uses pass 1 only;
  - a pass with fewer than 3 valid judges is dropped, and the run is not scored if no pass remains.

  | Confidence | When |
  | --- | --- |
  | **High** | Checks pass, 5 judges are valid, and within-one ≥ 80% |
  | **Low** | Checks fail, fewer than 4 judges are valid, or within-one < 50% |
  | **Medium** | Otherwise |

  The page says plainly that confidence measures judge agreement on the evidence, not ground truth.
- [ ] **AC8 Repeat stability.** `harness judge --passes N` judges N times. Each criterion then reports its mean ± standard deviation across passes [GRA §4.2]. With one pass, the standard deviation is N/A.
- [ ] **AC9 Judge calibration.** `harness calibrate <run_id>` builds perturbed dossiers, each with one planted defect, and judges them:
  The rubric's `calibration` map names the judged criterion each defect targets; a perturbation the map leaves out is `skipped`. A map entry naming a criterion that isn't judged is refused when the rubric loads. With our rubric:
  - **unscoped** targets `tool_arguments`: the area is removed from search arguments, and the results are relabeled as searched everywhere;
  - **fabricated** targets `grounding`: a named site is added that appears in no tool result, with coordinates inside the run's area so it isn't read as a scope violation;
  - **no_answer** targets `completeness`: the final answer is removed. The gate is not applied, so the judges' raw score is what's measured.

  A perturbation is **inconclusive** when the original median of its target is 0. Otherwise it **passes** when the perturbed mean median is lower than the original. `--passes N` averages out noise. Drops on non-target criteria are reported too. A perturbation is flagged **non-specific** when some other criterion drops as much as the target. Exit codes:
  - 0: nothing failed and at least one perturbation passed;
  - 1: a perturbation failed;
  - 2: nothing was testable.
- [ ] **AC10 Console on FastAPI.** `harness ui` serves a FastAPI app (T99), with endpoints:
  - start a run;
  - stream its events;
  - list runs;
  - open a run;
  - (re)judge a run;
  - serve its static report.

  Pages use the Tabler dashboard template and Tabler Icons. The Team Foundry name and logo are in the header and the favicon.
- [ ] **AC11 Plain-language trace.** Every step renders as one sentence built by code, with no LLM: what was asked, of which tool, in which area, and what came back. A toggle on each step shows its raw span JSON. Tool-specific wording lives in `tools/<server>/describe.py`, so the layering rule holds.
- [ ] **AC12 KPIs up front.** The top of a run page shows:
  - overall score and confidence;
  - agent cost and judging cost;
  - tool calls, with errors and retries;
  - model calls;
  - tokens in and out;
  - runtime;
  - claims verified;
  - claims in area, with the search footprint as a sub-line;
  - judge agreement.
- [ ] **AC13 Map.** A MapLibre map with Sentinel-2 cloudless and USGS imagery basemaps, and a layer switcher, draws:
  - the requested area's outline;
  - every LGND result's footprint, colored inside or outside the area;
  - coordinate claims as pins.

  Clicking a result opens its imagery tile, label, score and step. Clicking a step that returned results fits the map to them. The imagery attribution is shown.
- [ ] **AC14 Runs list and replay.** A runs page lists archived runs with model, status, score, cost and tool calls, and opens any of them from the archive alone. With networking off, an already-judged run renders fully: data, scores and timeline. All CSS and JS is vendored under `harness/web/static/vendor/`. Only map imagery needs the network.
- [ ] **AC15 Layering and docs.** The layer test covers the new modules. The README, a judging guide (rubric, panel, aggregation, confidence, calibration), the gap analysis against the briefs, and the handoff are current.

## Constraints

- Judges are Bedrock models reachable from the sandbox account and priced in `harness.yaml`. Prices come from the AWS Price List API, or from the pricing page when the API doesn't list the model.
- Judging one run costs under $1 per pass at default caps.
- Every first-party claim in the docs is cited or tagged, per the README convention.

## Open questions

- ADB's rubric and any reference answers for the task (owner: Clay/ADB, V191).
- Human expert ratings to validate the panel (owner: team, after the event).
