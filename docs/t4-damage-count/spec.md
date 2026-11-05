# T4 Damage Count: Scoring Per-Tier Counts After an Event: Spec

**Roadmap:** R12 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R1 (ADB answer keys: a labelled damage set is one)
**Size:** about 4 days of build, plus labelling one event block (about 1 day) and one live run

## Problem
After a disaster, post-disaster needs assessments (PDNA) and disaster risk finance need to know how many assets were damaged. They need those assets counted one by one, by a method that can be repeated quickly (Table 5) **[ext]**. The report's task T4 asks how many assets an event affected (Table 6). Its workflow compares before and after, and puts each asset in one tier: unaffected, damaged or destroyed (Table 9) **[ext]**.

An agent can be asked this today. The harness would judge its trace and check that the reported sites exist (`visual_confirmation`). Nothing checks whether its count per tier is right. A wrong count becomes a wrong first allocation figure **[team]**.

## Users
- **Primary:** PDNA and disaster risk finance analysts at ADB, deciding whether an agent's rapid count can stand as a first figure.
- **Secondary:** the LGND/Ode benchmark team, which has T4 in its battery.

## Goals
- An agent's per-tier counts, and its per-asset tiers, are scored against a held-out labelled set for one event.
- The analyst sees how far off each tier's count is, which affected assets were missed, and which tiers get confused.
- Repeat runs of the same prompt show how stable the count is, since PDNA needs a method that repeats quickly.

## Non-goals
- **Producing hazard or damage layers.** The report puts those out of scope (§2.2) **[ext]**. This effort evaluates an agent's count against labels; it publishes no layer of its own.
- **Loss estimates.** We report counts per tier and leave unit costs to the PDNA team (Table 5) **[ext]**.
- **New agent imagery tools,** such as Vantor search. The agent uses LGND's change tools as they are.
- **Tiering in the visual check.** The checker answers only present, absent or unclear.
- **A rubric change.** The metrics sit beside the score.

## User stories
- As a PDNA analyst, I want the agent's destroyed and damaged counts set against a labelled count, so that I know the error before I use the figure.
- As a disaster risk finance analyst, I want to see which affected assets the agent missed, so that I know where a field check is needed.

## Acceptance criteria
- [ ] **AC1 Damage set.** A reference set may declare `event` in `reference.json`: name, date, and the pre and post date windows. Each feature then carries a `tier` of `unaffected`, `damaged` or `destroyed`.
  - The loader refuses an event set if any feature has no tier or an unknown one, if the event date falls outside its post window, or if it breaks the licence rule.
  - Sets without `event` load unchanged.
- [ ] **AC2 Answer shape.** The T4 task prompt asks for two things:
  - each located claim to add `"tier"`;
  - the JSON block to add `"counts": {"unaffected": n, "damaged": n, "destroyed": n}`.

  A claim with no tier, or an unknown one, is listed as `untiered` and left out of the per-asset metrics.
- [ ] **AC3 Matching.**
  - **Per asset:** a tiered claim matches an asset when they share a 160 m cell, under the existing any-touch rule. When several claims touch one asset, it takes the most severe claimed tier, so each asset counts once.
  - **Counts:** stated counts are compared directly with the labelled counts.
- [ ] **AC4 Metrics.**
  - **Per tier:** count ratio (stated count ÷ labelled count), and the same ratio from the listed claims.
  - **Affected** (damaged plus destroyed): recall (affected assets matched to an affected tier ÷ affected assets) and precision.
  - **A 3×3 confusion matrix** over matched assets.
  - **`count_mismatch`:** set when the stated counts differ from the listed claims.
  - **An incomplete set** (its completeness is `incomplete`) reports precision and the confusion matrix only, never recall or count ratio.
- [ ] **AC5 Shown.** The run page and the static report show an "Against the event labels" card with the metrics, plus a map layer of labelled assets coloured by tier and marked found or missed. `GET /api/runs/{id}` includes `damage`, which is `null` when the run has no tie. The score is unchanged.
- [ ] **AC6 Repeatability.** `harness compare <suite>` adds, for a prompt run at least 3 times on one model, the spread of each tier's stated count (min, max, and coefficient of variation), plus the mean wall time and cost per run.
- [ ] **AC7 Replay.** Damage metrics come only from the snapshot in the run's archive, with no model or network call (`harness replay <id>`).
- [ ] **AC8 Licences.** The run's licence list includes the label set, with its imagery source as a "derived from" entry. Any run that used Vantor Open Data reads "check before sharing".
- [ ] **AC9 First set and live proof.** One event block of at least 100 hand-labelled buildings ships, built from imagery whose licence the loader accepts. Its `BUILD.md` records the pre and post images. One live AgentCore run on its T4 prompt is scored, and the handoff records the metrics, including whether LGND's change tools returned any results for the event's dates.

## Success signals
- **Metric (affected-count error):**
  - **numerator:** T4 runs whose card shows an affected count ratio and recall;
  - **denominator:** T4 runs tied to a damage set;
  - **target:** 100%.

  The value itself (count ratio per tier) is the analyst's figure, not a target.
- **Metric (planted check):**
  - **numerator:** fixture answers whose per-tier ratios and confusion matrix match hand calculation;
  - **denominator:** at least 6 fixtures (all correct; tiers swapped; nothing found; everything destroyed; listed and stated counts disagreeing; untiered claims);
  - **target:** 100%.

## Constraints
- **Licences:**
  - **Vantor Open Data** is CC BY-NC 4.0 (`harness/sharp.py:5-6`, `:51-56`). The report lists Maxar Open Data as needing permission (Table 4), and ADB outputs exclude non-commercial data (Table 1, §7.4) **[ext]**. Labels drawn from Vantor imagery can't ship as reference data until that's resolved.
  - **OpenAerialMap** items default to CC BY 4.0 but carry their own licence (`harness/sharp.py:197`).
- **LGND's indexes are NAIP and Sentinel-2** (`tools/lgnd/descriptors.py:83`). At 10 m, Sentinel-2 can't separate damaged from destroyed buildings, and NAIP isn't timed to events. So the agent may honestly be unable to tier, and the evaluator must score that as low recall, not as an error.
- **The scope is evaluation only** (report §2.2) **[ext]**.

## What exists today
- **LGND change tools** are in the tool list: `search_change_find`, `search_similar_change_find` and `discover_area_shift_find` (`tools/lgnd/descriptors.py:13-32`). All read an area (`:34-41`). The timeline describes them (`tools/lgnd/describe.py:57-58`, `:64-65`).
- **Vantor event imagery:** `harness/sharp.py:146-182` returns the newest image covering a point (`:181`), with no before and after pair.
- **The visual check** gives one verdict per site from `present`, `absent` or `unclear` (`harness/visual.py:40-41`). It's archived in `visual.json` (`analysis/judging/visual.py:15-23`).
- **Any-touch matching, completeness rules and count ratio** for a single class: `analysis/reference.py:283-332`. There's no tier or event field (`:75-120`).
- **The licence list per run**, which includes visual sources: `analysis/licences.py:169-186`, `:201`.
- **Compare** groups by concept and transfer role only (`analysis/report.py:197-248`).

## Assumptions and open questions
- **Assumption:** one block of about 100 buildings proves the method; PDNA use needs several events.
- **Assumption:** the agent's claims can carry an extra `tier` key without breaking provenance matching, which reads `value` and `ref`.
- **Open:** which event, and which imagery for labels? *Owner:* team, with LGND. *Default:* an event that has both OpenAerialMap post-event imagery under CC BY 4.0 and Sentinel-2 cover in LGND. Vantor is used only by the visual check in this sandbox.
- **Open:** may labels drawn from Vantor imagery be used as ADB reference data? *Owner:* Miguel, who asks Clay and LGND. *Default:* no.
- **Open:** does a building with partial damage count as "damaged" or "unaffected"? *Owner:* LGND/ADB. *Default:* "damaged" whenever any structural damage is visible, as written in `BUILD.md`.
- **Open:** should T4 cover assets other than buildings (bridges, substations)? *Owner:* Clay/ADB. *Default:* buildings first.
