# Climate Projections in Site Screening: Spec

**Roadmap:** H7 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H2](../hazard-tools/spec.md), [H3](../site-screening-task/spec.md).
**Size:** about 4 days

## Problem
Housing, schools and power plants last 30 to 80 years. A place that is low risk today may not be by 2050. Open projections exist ([catalog](../site-risk-sources/catalog.md#heat-drought-wildfire-water-and-climate-projections)) **[ext]**:
- **Flood:** Aqueduct for 2030, 2050 and 2080.
- **Cyclone:** STORM for 2050.
- **Heat and rain:** NEX-GDDP-CMIP6 at 0.25°, under four SSPs.
- **Sea level:** the IPCC AR6 projections to 2150.

H2's first release returns present-day values only, so an answer can't say how risk changes over the asset's life **[team]**.

## Users
- **Primary:** ADB and developers screening long-lived assets.
- **Secondary:** the evaluator, which checks that projected values are labelled with their scenario.

## Goals
- Every H2 hazard that has an open projection can be asked for a future year and scenario.
- Answers give present and future levels side by side, for the task's `horizon_years`.
- Heat stress and sea-level rise are added, as hazards with projections only.

## Non-goals
- **Downscaling of our own.** Published projections only.
- **Picking one scenario as "the" future.** The answer shows the scenarios it used.

## Acceptance criteria
- [ ] **AC1 Parameters.** `hazard_at` and `hazard_in` accept `year` (2030, 2050 or 2080) and `scenario`. Aqueduct takes RCP4.5 or 8.5; STORM's single projection is labelled SSP5-8.5; NEX-GDDP and AR6 take SSP1-2.6, 2-4.5, 3-7.0 or 5-8.5. A combination the source lacks returns a row naming what is available.
- [ ] **AC2 New hazards.** `extreme_heat` gives days per year above 35 °C maximum temperature, from the NEX-GDDP-CMIP6 ensemble median, with the model spread. `sea_level_rise` gives the median and the 17–83% range at the nearest AR6 grid point or tide gauge.
- [ ] **AC3 Answer.** H3's `hazards` items gain an optional `future` list: `year`, `scenario`, `level` and `evidence`. The verdict's reason names the future level whenever it is higher than today's.
- [ ] **AC4 Scored.** H4's level-consistency check covers `future` items. A projected value with no scenario is flagged `unlabelled_projection`.
- [ ] **AC5 Known answers.** Fixture tests cover:
  - a 2050 value;
  - a missing scenario;
  - a coastal point for sea level;
  - an inland point, which gets no sea-level row.
- [ ] **AC6 Live.** The Dhaka and Port Vila H3 runs are rerun with `horizon_years: 50`. Their present and future levels are recorded in the handoff.

## Success signals
- **Metric (labelled futures):**
  - **numerator:** future values in answers that carry a year and scenario;
  - **denominator:** all future values in answers;
  - **target:** 100%.

## Constraints
- **Licences:** NEX-GDDP on AWS is CC0. AR6 sea level and Aqueduct are CC BY 4.0. STORM is CC0.
- **Uncertainty:** projections are ranges. The answer gives the spread where the source has one.

## What exists today
- None beyond H2.

## Assumptions and open questions
- **Open:** which scenario is the default when the task names none? *Owner:* Clay/ADB. *Default:* SSP2-4.5, with SSP5-8.5 alongside.
