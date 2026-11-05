# Uncertainty Calibration — Spec

**Roadmap:** R6 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R1 (ADB answer keys) for the calibration half · **Size:** M (about 5 days, plus one live run, about $0.55)
**Background:** [what the LGND/Ode inception report means for Track 1](../adb-alignment/lgnd-ode-brief.md)

## Problem
An ADB analyst reading an agent's answer can't tell how far to trust its size. Answers list sites and may hedge in prose, but they never state a count with a range, and nothing checks whether stated confidence matches the error against a reference. The only signal is a judge's opinion of how honest the answer sounds. Run `79c18997` (Pecos County solar, 2026-11-05) shows the cost. The panel scored it 99.4 with High confidence, yet the agent found 5 of the county's 12 facilities. An analyst who sized exposure from that answer would undercount by two thirds with no warning. The benchmark requires both halves: record whether uncertainty is stated, and whether it matches the error observed against reference data (§4.2, requirement 3) **[ext]**.

## Users
- **Primary:** ADB analysts and the LGND/Ode benchmark team, who read an agent's count next to the benchmark's ranged counts (§5.5) **[ext]**.
- **Secondary:** the team, comparing models across a suite.

## Goals
- Every new answer states how many assets it believes are in the area, with an 80% range, and a confidence for each reported site.
- Where a complete reference exists, each run records whether the reference count fell inside its stated range, and each suite reports how often that happens against the 80% it claimed.
- Per-site confidence is scored against reference outcomes, so overconfident agents show a measured gap, not only a judged one.

## Non-goals
- **No rubric change.** These metrics sit beside the score, as the reference metrics already do. The judged `calibration` criterion stays as it is.
- **Showing reference outcomes to the judges** (it would leak the answer key into the panel).
- **Ranges for derived totals** such as count × area (that is R10).
- **Rescoring or re-prompting old runs.** Runs made before this change are recorded as "not stated".
- **Choosing the agent's method** for estimating a range. We measure what it states.

## User stories
- As an ADB analyst, I want a count with a range, so that I can carry the uncertainty into exposure estimates.
- As the benchmark team, I want to know whether an agent's 80% ranges contain the truth about 80% of the time, so that I can compare its honesty with our workflows.
- As an evaluator, I want overconfident sites to show as a number, so that a confident wrong answer is visible without reading the prose.

## Acceptance criteria
- [ ] **AC1 Answer contract.** `prompts/agent/system.md` asks for a top-level `estimate` object in the claims block: `{"count": int, "low": int, "high": int, "level": 0.8}`. It counts distinct assets of the requested type inside the requested area. Each claim whose value is a "lat, lon" pair may carry `"confidence"`, a number in [0, 1] that the site is a real asset of that type. `analysis/provenance.py` stays the only parser. An `estimate` is **valid** when 0 ≤ low ≤ count ≤ high and level is exactly 0.8. Anything else is recorded as `invalid` with the reason. A missing `estimate` is recorded as `not_stated`.
- [ ] **AC2 Stated.** Every run's report has `uncertainty.stated`: `valid`, `invalid` or `not_stated`, and per-site confidences: given / located sites. This is recorded whether or not a reference is tied.
- [ ] **AC3 Interval check.** Given a run tied to a **complete** reference with a valid estimate, the report records `reference_count` (the reference's `assets` inside the area), `in_range` (low ≤ reference_count ≤ high, inclusive) and `count_error` ((count − reference_count) ÷ reference_count, to 3 decimals). With an incomplete reference, these are null, with the note "reference is incomplete: the range can't be checked".
- [ ] **AC4 Site outcomes.** Given a complete reference, a located claim with a confidence has outcome 1 when its 160 m cell is a flagged cell touching a reference asset (the existing rule in `analysis/reference.py`). Otherwise its outcome is 0. Claims outside the reference area are excluded. Per run, the report shows the Brier score: the mean of (confidence − outcome)², to 3 decimals, over n sites.
- [ ] **AC5 Suite calibration.** `harness compare <suite>` writes `uncertainty.csv` with one `suite` row and one row per concept. Its columns: `runs`, `stated_valid`, `range_scored`, `in_range`, `coverage` (in_range ÷ range_scored), `coverage_gap` (coverage − 0.8), `sites_scored`, `brier`, and `ece`. ECE uses 5 equal-width confidence bins and is Σ (n_bin ÷ N) × |mean outcome − mean confidence|. `coverage` is empty when range_scored < 5, and `ece` when sites_scored < 20. The `note` column then says which is too few.
- [ ] **AC6 Shown.** The run view's "Against the reference" card shows "Stated 9 (range 6–14); reference 12: inside the range". It shows "outside" when the count isn't in range and "No range stated" when there's no valid estimate. The judged `calibration` score is unchanged and sits beside it. `GET /api/runs/{id}` returns the `uncertainty` object, and the static report shows the same line.
- [ ] **AC7 Offline and stable.** All values are computed from the run's archive and its reference snapshot. `harness replay` reproduces them byte for byte, and runs made before this change show `not_stated` with no error.
- [ ] **AC8 Live proof.** One new AgentCore run of `prompts/tasks/adb/pecos-solar.md`, tied to `uspvdb-tx-pecos-v4`, has `stated: valid`, an `in_range` value and a Brier score. Its numbers are in the handoff.

## Success signals
- **Metric (valid-estimate rate):** in the first suite run after release:
  - numerator: runs with `stated: valid`;
  - denominator: runs with status `ok`;
  - target: ≥ 90%.
- **Metric (range-scored share):** runs with `range_scored` ÷ runs tied to a complete reference, over the same suite. The target is 100%; anything less means a parsing or tie defect.

## Constraints
- Recall-type checks are defined only against complete reference data (§7.2.1) **[ext]**. A count range is a recall-type check, so it obeys the same rule.
- The benchmark's aggregation reports a count with a range (§5.5, Table 9) **[ext]**. The fixed 80% level is our choice **[team]**.
- The prompt change alters agent behaviour, so scores of runs from before and after the change aren't strictly comparable. The prompt is versioned like other prompt changes.
- The cost is one live run, about $0.55 (agent plus judging, the average of suite `adb-t1-v1-20261105T1103`).

## What exists today
- `calibration` is a **judged** criterion: "states uncertainty and limits honestly" (`rubrics/geo-dataset-v1.yaml:83-91`). The rubric's separate `calibration:` map is for planted defects (`rubrics/geo-dataset-v1.yaml:133-137`, `harness/calibrate.py:3`). This feature uses the word "uncertainty" in its fields to avoid that clash.
- The claims block holds `claim`, `value` and `ref` only, one verbatim value per claim. It has no count, range or confidence (`prompts/agent/system.md:12-19`). Its single parser is `analysis/provenance.py:1-3,149`.
- Reference scoring already has the asset count, the flagged cells and the asset cells. Recall and count ratio are gated on `complete` (`analysis/reference.py:283-335`, gate at `:312`). Count ratio uses distinct flagged sites, not a stated count (`analysis/reference.py:314`).
- `harness compare` writes `compare.csv`, `concepts.csv` and `compare.html` (`harness/cli.py:102-132`).
- The only shipped reference is `references/uspvdb-tx-pecos-v4/` (complete, 12 facilities).

## Assumptions and open questions
- Assumption: agents follow a structured-output instruction for a new key as reliably as for `claims`. If the valid rate stays below 90%, add a parse-and-retry like the visual check's (`prompts/harness/visual_check_retry.md`).
- Assumption: complete reference sets are rare until R1 delivers ADB answer keys. Until then, coverage rests on Pecos and is mostly "too few".
- Open: fix the level at 80%, or let the agent choose? — owner: team; default: fixed at 0.8, so coverage pools across runs.
- Open: should an out-of-range count lower the score or cap `calibration`? — owner: user; default: no, the metrics sit beside the score.
- Open: score site confidence against incomplete references, where an unmatched site may be a real but unlisted asset? — owner: team with LGND; default: complete references only.
