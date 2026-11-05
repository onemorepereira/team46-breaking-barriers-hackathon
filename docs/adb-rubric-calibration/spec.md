# ADB Rubric Drop-in and Expert Calibration: Spec

**Roadmap:** R15 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R9 (ADB deployment profile: its archive holds ADB's reviews and guidance). It's blocked externally on Clay for ADB's rubric (V191) and on ADB for expert time.
**Size:** about 3 days of build, plus about 10 expert-hours (20 runs × 2 experts × about 15 minutes)

## Problem
Every score the harness gives comes from a rubric ADB didn't write and a judge panel no expert has checked:
- **The rubric:** ADB's rubric and task were promised but never arrived (V191; docs/judging/gaps.md:49) **[event]**.
- **The panel:** its trust rests on agreement between judges and on planted defects (docs/judging/paper-notes.md:17, :26).
- **The benchmark for that trust:** the GRA paper validated its autorater against domain experts, whose own agreement was α ≈ 0.56. We've never measured ours.

When ADB's rubric does arrive, there's no procedure for checking that the panel applies it the way ADB's reviewers would. So ADB can't tell whether a score of 90 means what its own experts would mean by it **[team]**.

## Users
- **Primary:** ADB's domain experts and the analysts who rely on scores (V29) **[event]**.
- **Secondary:** Clay, owning the rubric hand-off; the team, running the calibration.

## Goals
- ADB's rubric runs as a YAML file, with no code change, wherever its criteria are judged or among the four measured ones.
- Panel–expert agreement is measured on about 20 runs, with a confidence interval, against the experts' own agreement.
- ADB reviewers' disagreements become judge guidance through the existing propose, evaluate and approve loop.

## Non-goals
- **Writing code for new measured criteria** that ADB's rubric introduces. Each one becomes its own effort, and the drop-in refuses it with the existing error.
- **Changing aggregation, gates or confidence.**
- **Choosing ADB's experts** or paying for their time.
- **Mixing ratings across rubrics.** Ratings under `geo-dataset` v3 don't count for ADB's rubric.
- **New judge models.**

## User stories
- As Clay, I want to drop ADB's rubric into `rubrics/` and switch to it in config, so that every new judgement uses it the same day.
- As an ADB expert, I want to rate a run without seeing the panel's scores, so that my rating isn't anchored on theirs.
- As an ADB analyst, I want to see how far the panel is from our experts, next to how far our experts are from each other, so that I know whether to trust a panel score.

## Acceptance criteria
- [ ] **AC1 Drop-in.** Suppose ADB's rubric is saved as `rubrics/adb-<name>-v1.yaml` and `judging.rubric` points at it, in `harness.local.yaml` or the ADB profile.
  - **It works:** `harness judge <run>` scores with it, `harness calibrate <run>` plants defects against its `calibration` map, and the console shows its criteria. None of this needs a code change.
  - **Its header comment** maps each of its criteria to the report's §5.8 dimensions and to the nearest `geo-dataset` v3 criterion.
  - **What's refused:** a criterion marked measured that code doesn't know, refused with the existing error naming it.
  - **Missing calibration map:** if the rubric has no `calibration` map, `calibrate` reports every perturbation as "skipped".
- [ ] **AC2 Calibration set.** A committed `calibration/adb-v1.yaml` lists 20 archived, judged run IDs, and a test checks that the list:
  - covers at least 4 concepts and at least 3 places outside the US;
  - has at least 5 runs scoring under 70 and 5 scoring 90 or more, under the active rubric;
  - includes no run that has been reconsidered.

  `harness judge --calibration adb-v1` re-judges every listed run under the active rubric. It shows the estimated cost first and asks to confirm (`--yes` skips).
- [ ] **AC3 Blind rating.** A blind review mode, as `harness review --blind` or the console's review card opened with `?blind=1`:
  - hides the panel's scores, votes, reasons and confidence until the review is submitted;
  - disables "agree";
  - requires a score for every judged criterion;
  - stores `blind: true` on the review.

  A test asserts that the blind review API response before submission contains no panel score.
- [ ] **AC4 Agreement report.** `harness agreement --human --calibration adb-v1` reports, from blind reviews only:
  - **inter-expert α** (ordinal, over runs with at least 2 experts, with a 95% cluster-bootstrap CI by run);
  - **panel–expert α** (the panel median against the expert lower median), with its CI;
  - mean absolute difference and exact share, overall and per criterion;
  - the run count and reviewer count.

  It writes `out/calibration/adb-v1/agreement.csv`. Blind and non-blind reviews are never pooled, and results are grouped by guidance version, as now.
- [ ] **AC5 Verdict.** The report states **calibrated** when all three hold:
  - panel–expert α is at least inter-expert α minus 0.05;
  - no criterion's panel–expert mean absolute difference is over 0.5 on the 0 to 2 scale;
  - at least 10 runs have 2 or more experts.

  Otherwise it states **not calibrated**, naming each failing condition, or **not enough ratings**.
- [ ] **AC6 Guidance.** ADB's blind reviews of train runs feed `harness guidance propose`. The resulting version goes through `guidance evaluate` on the held-out runs and `guidance approve` with an ADB approver's name, all through the existing flow. The approved version and its evaluation are stored in the ADB deployment's archive only. After approval, AC4 is re-run on held-out runs to show the before and after.
- [ ] **AC7 Stand-in run.** Before ADB's rubric and experts arrive, the whole procedure (AC2 to AC6) runs once on `geo-dataset` v3 with 2 team reviewers. Every output from it is labelled "team stand-in, not ADB experts". The handoff records the numbers and the cost.

## Success signals
- **Metric (held-out exact agreement):**
  - **numerator:** held-out (run, judged criterion) units where the panel median equals the expert lower median, from blind reviews under ADB's rubric;
  - **denominator:** all held-out units with both scores;
  - **target:** at least the inter-expert exact share on the same units.
- **Metric (guidance effect):**
  - **numerator:** criteria whose held-out panel–expert mean absolute difference falls after the approved guidance;
  - **denominator:** judged criteria with held-out ratings;
  - **target:** at least half, with no criterion rising by more than 0.25 (the existing rule).

## Constraints
- **ADB's rubric** comes from Clay (V191; Technical brief, T31) **[event]**.
- **The expert bar:** α ≈ 0.56 among experts in the GRA paper, §4.1.4 (docs/judging/paper-notes.md:17). It's a reference point; our verdict uses our own experts' α.
- **Cost:** re-judging 20 runs is about 20 × $0.31 (`harness/feedback.py:32`), plus one guidance evaluation of twice the held-out runs plus 4 passes (`harness/feedback.py:578`). The estimate is shown before any spend.
- **Guidance** stays in the deployment's own archive (docs/judge-feedback/spec.md, AC13).

## What exists today
- **The rubric loader:** judged criteria need anchors on every scale point. Measured criteria must be one of `claim_provenance`, `area_compliance`, `condition_compliance` or `visual_confirmation` (`analysis/judging/rubric.py:15-20`, `:97-98`). The calibration targets are validated at `:112-118`.
- **The active rubric** is set in config (`harness.yaml:50`). The current one declares a calibration map (`rubrics/geo-dataset-v1.yaml:134-137`) and says ADB's rubric replaces it (`:1-4`).
- **Reviews and guidance are keyed by rubric id and version** (`harness/feedback.py:128`, `:313-314`, `:380-381`), so v3 ratings don't carry over.
- **"Agree" copies the panel median** (`analysis/judging/feedback.py:77-80`), and the review card shows the panel's scores, so ratings today are anchored.
- **Human scores** collapse reviewers to a lower median per criterion (`analysis/judging/feedback.py:234-266`). There's no inter-reviewer α.
- **Panel–human α** with a bootstrap CI: `analysis/judging/feedback.py:278-309`, shown by `harness agreement --human` (`harness/cli.py:377-392`).
- **The held-out split** is a third, by run ID (`analysis/judging/feedback.py:220-224`). At least 5 held-out runs are needed (`harness/feedback.py:31`).
- **Planted-defect calibration** is in `harness/calibrate.py:1-5`, `:95`, and the feedback check at `:208`.

## Assumptions and open questions
- **Assumption:** ADB's rubric uses an integer scale with anchors, like ours. If it uses free text or weights, the loader needs code, and that's a separate effort.
- **Assumption:** about 7 of 20 runs fall in the held-out third, which clears the 5-run minimum.
- **Open:** when does ADB's rubric arrive, and in what form? *Owner:* Clay. *Default:* `geo-dataset` v3 stays active, and AC7 runs on it.
- **Open:** who are the experts, and how many per run? *Owner:* Clay/ADB. *Default:* 2 per run on all 20 runs.
- **Open:** are AC5's thresholds right? *Owner:* Clay/ADB. *Default:* as written. They're recorded in `calibration/adb-v1.yaml`, so they can change without code.
- **Open:** should experts rate the visual and measured checks? *Owner:* team. *Default:* no. Those are measured by code, and reviewers comment on them in the measured-checks note.
