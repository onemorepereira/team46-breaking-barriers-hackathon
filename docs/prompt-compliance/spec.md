# Slice: Do the Results Honor Every Condition in the Prompt?

**Status:** Open · **Owner:** unassigned · **Size:** about a day (split point in Plan below) · **Branch:** `slice/prompt-compliance` from `main` · **Merges:** second, after plain language (rebase on its rubric changes)
**Read first:** [how a run is scored](../judging/guide.md), [developer guide](../developer-guide.md), the [factory rules for slices](../factory.md#how-to-take-a-slice).

## Problem
Take the prompt "data centers **within 10 miles of a protected natural area**, **within ZIP 75082**". It sets three conditions:
1. the target is a data center;
2. it sits inside ZIP 75082;
3. it lies within 10 miles of a protected natural area.

The evaluator only checks condition 2 in code (`area_compliance`: is each claimed site inside the area?). Conditions 1 and 3 are left to the judges' general sense of "result relevance". So a run can claim sites that ignore condition 3 entirely and still score well. ADB needs to see, **condition by condition, whether the trace holds evidence for each result**, and to see "no evidence" when there's none.

## What exists today (start here)
- **Area resolution:** `harness/area.py` reads one area from the prompt (`extract_area` with `prompts/harness/area_extract.md`, then `resolve_area` against OpenStreetMap or the US Census) and archives it in the run's manifest (`snapshot.search_area`).
- **Measured criteria:** `analysis/judging/measure.py` computes `claim_provenance` and `area_compliance`. The rubric names measured criteria with `kind: measured`, and the loader (`analysis/judging/rubric.py`) refuses unknown measured IDs. A new one needs both code and rubric changes.
- **Claims:** they come from `analysis/provenance.py`. Each claim has a value, a cited tool result (`ref`, e.g. `T3`) and a status, and coordinates are parsed by `core.geometry.coordinate_pair`. Point-in-polygon is `core.geometry.contains`. There's **no distance function yet**.
- **What the judges read:** `analysis/judging/dossier.py` builds it, and the judges never see measured results.
- **Model calls from the harness:** these use prompt files in `prompts/harness/` loaded with `core.prompts.load`. Tests fake Bedrock (see `tests/test_judging.py:FakeBedrock`).

## Acceptance criteria
- [ ] **AC1 Conditions are extracted once, then archived.** A new step reads the prompt into a list of conditions, using a new `prompts/harness/conditions_extract.md` with the `narrative_model`. Each condition is one of:
  - `target` (e.g. "data center");
  - `inside_area` (the area already resolved);
  - `within_distance` (`distance_km`, plus a reference feature such as "protected natural area");
  - `other` (kept as text, judged only).

  The list is written to `runs/<id>/conditions.json` when a new run's report is first written. Replay and re-judge read the file and never call the model again. A prompt with only an area gives `[target, inside_area]`. **Runs archived before this slice have no file:** they show no conditions table, and `condition_compliance` is N/A for them. No extraction happens on replay.
- [ ] **AC2 A claim × condition evidence matrix, computed by code.** For every coordinate claim and every condition, a status (`supported`, `contradicted` or `unverified`), the reason in a few words, and the step refs used:
  - `inside_area`: the existing point-in-polygon check;
  - `within_distance`: `supported` only if the trace holds **a located reference feature**, meaning a tool result or claim with coordinates for it, and the great-circle distance (new `core.geometry.distance_km`, haversine, unit-tested against known pairs) is within the limit. `contradicted` if every located reference is too far. **`unverified` if the trace has no located reference at all.** The trace must show the evidence; the evaluator doesn't assume it;
  - `target` and `other`: `unverified` in code. The judges assess them (AC4).
- [ ] **AC3 A new measured criterion.** `condition_compliance` is the share of claim × condition cells that are `supported`, over the code-checked conditions only. It's N/A when the prompt has no condition beyond the area. It's added to the rubric as **`version: 2`** (an int: the loader requires one, and every judgement records it). Measured criteria have no `calibration` entry; that map is for judged criteria. It appears in the scorecard and confidence like the other measured criteria. Existing archived judgements still re-aggregate (test).
- [ ] **AC4 Judges judge against the conditions.** The dossier gains a "Conditions in the request" section listing the extracted conditions (not the matrix, so code and judges stay independent). The `result_relevance` and `completeness` anchors in the rubric say to judge each condition. **This is the one accepted change to how existing criteria are scored**, and it's why the version goes to 2: judgements made under version 1 stay comparable only with each other. `harness calibrate` still passes on a known-good run (it needs live Bedrock in [your own sandbox](../factory.md#your-own-aws-sandbox)).
- [ ] **AC5 Visible.** The run page has a "Conditions" table (claims as rows, conditions as columns, a status icon plus its reason on hover), and so does the report. Unverified cells say why, e.g. "no protected area located in the trace".
- [ ] **AC6 The example works live.** Run "Find data centers within 10 miles of a protected natural area within ZIP 75082" (local backend). The matrix must show condition 3 as `unverified` or `contradicted` for any claim the trace doesn't support, and the handoff records the run ID and the matrix. Tests cover all three statuses with fixtures (no network).

## Non-goals and boundaries
- **Not fetching outside data** to check reference features independently (e.g. PAD-US protected areas). This slice only checks what the trace contains. A follow-up can add an independent check.
- No change to the agent, its tools or its prompts (`agent/`, `tools/`, `prompts/agent/`), and no AgentCore redeploy.
- No other change to how the existing criteria are scored (AC4's anchor wording is the one exception).

## Plan (with a split point if time runs short)
1. **2a, shippable alone:** AC1, AC2 (with `distance_km`), and AC5's table, all from code.
2. **2b:** AC3 (the measured criterion and rubric 1.1), and AC4 (the dossier section and rubric anchors), then `harness calibrate`.
3. AC6, run live.

## How to check your work
```sh
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run harness run --prompt <your-prompt-file.md> --model sonnet --backend local   # needs AWS credentials
uv run harness calibrate <a-known-good-run-id>
```

## When done
Write `docs/prompt-compliance/handoff.md` (each AC with its proof, the AC6 run ID and matrix), set Status to `Built`, update [the factory](../factory.md), and open a PR to `main`.
