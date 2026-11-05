# Site-Screening Task and Answer Format: Spec

**Roadmap:** H3 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H2](../hazard-tools/spec.md) (hazard tools).
**Size:** about 3 days

## Problem
Today's tasks ask "find every X in this area" (`prompts/tasks/`). A site-risk question is different: "Should I invest in this area to build [housing, a power plant, a solar or wind farm, a school], or is the risk of natural and man-made disasters too high?" **[team]**

The answer is a judgement over several hazards, weighed for the kind of asset. A school cares about earthquakes and floods during occupancy; a solar farm about hail, flood and wind; a coastal power plant about surge and sea-level rise. Without a fixed answer shape, two runs can't be compared, and an evaluator can't tell a well-founded "too risky" from a guess **[team]**.

## Users
- **Primary:** ADB and developers screening sites before due diligence.
- **Secondary:** the evaluator ([H4](../site-risk-scoring/spec.md)), which scores answers in this format.

## Goals
- A site-screening task names the place (point, area, postal code, municipality or region) and the asset type. The agent answers in a fixed, machine-readable shape.
- The answer rates each relevant hazard, with the tool values behind the rating. It gives an overall screening verdict and its confidence, and says what it could not assess.
- Hazard relevance per asset type is written down once, not reinvented by each run.

## Non-goals
- **Investment advice.** The verdict is a screening flag for further study, not a decision. The answer says so.
- **Site engineering** (foundations, design return periods). That needs local codes and surveys.
- **Cost or financial return.** The question is risk only.
- **Resource quality** (solar irradiance, wind speed) as a reason to build. It may be cited as context, not weighed.

## Acceptance criteria
- [ ] **AC1 Task file.** A site-screening task is a prompt file in `prompts/tasks/site-risk/` with front matter: `kind: site_screening`, `place` (text or GeoJSON), `asset_type` (one of AC2), and optional `horizon_years` (default 30). It loads like the existing task files.
- [ ] **AC2 Asset profiles.** `prompts/tasks/site-risk/assets.yaml` lists, for each asset type, which hazards matter and why. Types: `housing`, `school`, `hospital`, `solar_farm`, `wind_farm`, `thermal_power_plant`, `substation`, `road`, `warehouse`. Each hazard is `primary` or `secondary` for that type, with a one-line reason. The profiles are cited, where a source exists, or tagged **[team]**.
- [ ] **AC3 Answer shape.** The agent's final answer ends with a fenced JSON block, `site_screening`, with:
  - `place`: as resolved, with its area or point;
  - `asset_type`;
  - `hazards`: a list. Each item has `hazard`, `level` (`very_low`, `low`, `medium`, `high`, `very_high` or `not_assessed`), `evidence` (the tool values with units, return periods and `source_id`), and `relevance` (`primary` or `secondary`, from AC2);
  - `exposure`: population and built-up area, where known;
  - `verdict`: `proceed`, `proceed_with_mitigation`, `detailed_study_needed` or `avoid`;
  - `confidence`: `low`, `medium` or `high`, with a reason;
  - `not_assessed`: hazards with no data here, and why;
  - `limits`: resolution, data dates and licence notes.
- [ ] **AC4 Levels.** `prompts/tasks/site-risk/levels.yaml` maps each H2 metric to the five levels, with thresholds cited to their source. For example, flood depth at 100 years: 0 m very low, under 0.15 m low, under 0.5 m medium, under 1.5 m high, otherwise very high. The agent is told the thresholds, so levels are repeatable.
- [ ] **AC5 Parse.** `analysis/site_risk.py` parses the block and reports, by field, any missing field, unknown level or unknown hazard. A run whose answer has no block is scored with a `format` issue, not crashed.
- [ ] **AC6 Example cards.** Six site-screening cards are added to the console:
  - housing in Dhaka;
  - a school in Kathmandu;
  - a solar farm in Rajasthan;
  - a wind farm in Ilocos Norte;
  - a substation in Port Vila;
  - housing in Harris County, Texas (the US check against FEMA's index in H4).
- [ ] **AC7 Live.** One run per card completes on AgentCore, with a parsed answer. The verdicts and the hazards rated are recorded in the handoff.

## Success signals
- **Metric (well-formed answers):**
  - **numerator:** site-screening runs whose answer parses with no issues;
  - **denominator:** all site-screening runs;
  - **target:** 90% or more.
- **Metric (relevant hazards covered):** in parsed answers, the share of the asset's `primary` hazards that are rated or listed in `not_assessed`. **Target:** 100%.

## Constraints
- **Place types:** postal codes and municipalities resolve through the existing area lookup (`harness/area.py`), which accepts boundaries and places only (commit `c041b6f`).
- **Wording:** the answer's prose and the verdict are in plain language. The plain-verdict pattern ([plain verdict](../plain-verdict/spec.md)) applies.

## What exists today
- **Task prompts:** `prompts/tasks/` (Dallas data centres, the ADB suite, controls).
- **Area resolution:** `harness/area.py`.
- **Condition extraction from prompts:** `prompts/harness/conditions_extract.md`, used by prompt compliance.
- **Example cards:** [example cards](../example-cards/spec.md).

## Assumptions and open questions
- **Open:** whose level thresholds? *Owner:* Clay/ADB. *Default:* thresholds from the sources' own guidance where it exists, otherwise **[team]** values, flagged in `levels.yaml`.
- **Open:** should the verdict weigh exposure (people at risk) or only hazard? *Owner:* ADB. *Default:* hazard decides the level; exposure is reported beside it and named in the confidence reason.
- **Assumption:** a 30-year horizon fits the asset types listed. Housing and schools outlive it, so `horizon_years` is overridable.
