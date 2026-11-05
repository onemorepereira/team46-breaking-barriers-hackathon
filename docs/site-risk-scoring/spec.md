# Evaluating Site-Risk Answers: Spec

**Roadmap:** H4 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H3](../site-screening-task/spec.md) (the answer format); [H8](../site-risk-validation/spec.md) for the measured half.
**Size:** about 5 days

## Problem
The evaluator scores "find every X" runs: claim provenance, area and condition compliance, the visual check, and answer keys (`rubrics/geo-dataset-v1.yaml`, `analysis/reference.py`) **[team]**. None of that applies to a site-risk answer. Its claims are hazard levels and a verdict, not sites.

A confident "proceed" for a school on a floodplain is the most harmful error here, and the current rubric wouldn't catch it. Without an evaluator, a site-risk agent is as unaccountable as the datasets this project exists to check **[team]**.

## Users
- **Primary:** ADB and developers deciding whether to trust an agent's screening.
- **Secondary:** LGND and agent builders comparing models on the task.

## Goals
- Every site-screening run gets a judged score under its own rubric, plus measured checks that don't depend on the judges.
- **Measured:**
  - each number in the answer is traced to a tool result;
  - each level follows from its number under the published thresholds;
  - each primary hazard is covered.
- **Where an answer key exists** (FEMA's National Risk Index in the US; past events elsewhere, from H8), the answer's levels and verdict are scored against it.
- Errors that understate risk are weighted more than errors that overstate it, and the report says which one a run made.

## Non-goals
- **Deciding the true risk.** The evaluator compares with references, which have their own limits, and says so.
- **New judges.** The existing panel and its recusal rules are reused.

## Acceptance criteria
- [ ] **AC1 Rubric.** `rubrics/site-risk-v1.yaml` has these criteria:
  - `hazard_coverage`: primary hazards rated or explained;
  - `value_provenance`: numbers traced to tools;
  - `level_consistency`: levels follow the thresholds;
  - `asset_fit`: the hazards weighed suit the asset;
  - `uncertainty_and_limits`: resolution, data age and gaps stated;
  - `verdict_support`: the verdict follows from the levels;
  - `licence_compliance`.

  The first four are measured. Runs with `kind: site_screening` use this rubric automatically.
- [ ] **AC2 Measured checks.** `analysis/site_risk.py` computes, per run:
  - **Provenance:** the share of `evidence` values that match a hazard tool result (via `analysis/provenance.py`).
  - **Level consistency:** the share of levels that equal the level implied by their evidence under `levels.yaml`.
  - **Coverage:** the share of primary hazards rated or listed in `not_assessed`.

  Each is shown with the failing items named.
- [ ] **AC3 US answer key.** For a US place, the answer's level per hazard is compared with FEMA's National Risk Index rating for the census tract (or county) holding the place. The comparison reports:
  - the agreement per hazard, exact and within one level;
  - weighted Cohen's kappa over all hazards rated in a suite;
  - **understatement:** hazards the answer rated two or more levels below the index.

  The index (v1.20) is staged from OpenFEMA with its version.
- [ ] **AC4 Past-event key.** Where H8 provides past events for a place, the report lists events at the place since the hazard data's date (cyclone tracks within 50 km, flood footprints, shaking above a set level). It flags any hazard the answer rated `very_low` or `low` that has such an event.
- [ ] **AC5 Verdict check.** A verdict of `proceed` while any primary hazard is `high` or `very_high` is flagged `verdict_unsupported`. The flag lowers `verdict_support` and is shown in the plain summary.
- [ ] **AC6 Shown.** The run page, static report and workspace show a site-risk section. It holds a hazard table (the answer's level, the measured level and the reference level, side by side), the verdict and its flags, and the measured checks. `GET /api/runs/{id}` returns them under `site_risk`. `harness compare` adds `kappa`, `understatement` and `verdict_unsupported` columns.
- [ ] **AC7 Planted defects.** Five planted-defect answers each lower the score and name the defect:
  - an invented flood depth;
  - a wrong level for its number;
  - a missing primary hazard;
  - `proceed` with a very-high flood rating;
  - a non-commercial source under `profile: adb`.
- [ ] **AC8 Live.** The six H3 example runs are judged. Their scores, kappa (Harris County) and flags are recorded in the handoff.

## Success signals
- **Metric (catches understatement):**
  - **numerator:** runs flagged for understatement against FEMA's index, or for an unsupported verdict, that a reviewer confirms;
  - **denominator:** all runs so flagged;
  - **target:** 80% or more.
- **Metric (agreement with FEMA):** weighted kappa over the H8 US places, reported per model. No target; it is the comparison LGND and ADB would read.

## Constraints
- **FEMA's index is US-only** and county or tract scale. It can't judge a single site, so AC3 reports at tract scale and says so.
- **Asymmetry:** understating risk costs lives and assets; overstating it costs a missed investment. The rubric weighs `verdict_unsupported` more heavily than the opposite error. The weights are in the rubric file **[team]**.

## What exists today
- **Rubric and judges:** `rubrics/geo-dataset-v1.yaml`, `analysis/judging/` (panel, recusal, measured criteria).
- **Claim provenance:** `analysis/provenance.py`.
- **Planted-defect calibration:** the judging calibration set ([judging](../judging/spec.md)).
- **Licence lists:** `analysis/licences.py`, extended by [H1](../site-risk-sources/spec.md).

## Assumptions and open questions
- **Open:** how should FEMA's five ratings map to our levels? *Owner:* team. *Default:* one to one (Very Low to Very High). Its "Insufficient Data" and "Not Applicable" ratings are left out of agreement.
- **Open:** does ADB have an answer key for Asia-Pacific (for example from the Disaster Risk Analytics Explorer)? *Owner:* Miguel, who asks Clay/ADB. *Default:* past events from H8 only.
