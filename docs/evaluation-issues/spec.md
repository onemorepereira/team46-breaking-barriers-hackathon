# Jump to problem areas in the Evaluation panel — Spec

**Track:** Quick   **Product stage:** Introduction
**Status:** Built   **Last updated:** 2026-11-05

## Problem
A reviewer reading a run's Evaluation panel sees about 13 collapsed sections. Weak questions (e.g. grounding 83), unverified conditions, licence blockers, failed judges and reference misses hide inside them. The only way to find them is to open one section at a time.

## Design review
The user chose **"Badges + filter"** on 2026-11-05, over a needs-attention list and issue chips:
- each section title shows a red count of its issues;
- a toggle shows only the sections with issues.

## Acceptance criteria
- [ ] **AC1 Counts.** `sectionIssues(view)` in `frontend/src/api.ts` returns a count per section id, from data the run view already carries:
  - `rubric`: criteria with a numeric score below 100;
  - `conditions`: condition cells `contradicted` or `unverified`, plus 1 when the check is `not_checked` or has an `error`;
  - `judges`: judges whose status isn't `ok`, plus 1 when reliability is `Low` or `judges_in_doubt`;
  - `failures`: fatal gates, plus failure modes, plus 1 when tool errors > 0;
  - `reference`: missed reference IDs, plus 1 when the reference has an `error`;
  - `licences`: the number of licence blockers when `presentable` is false (at least 1).
  
  Every other section counts 0. Unit tests cover each rule and an unjudged run (all 0).
- [ ] **AC2 Badges.** A section with a count > 0 shows a badge with the number after its title. It uses the danger colour with white text, and has an accessible name ("{n} issues"). Sections with 0 show nothing. Inside the rubric section, each criterion below 100 shows a small dot badge.
- [ ] **AC3 Filter.** Above the sections, a checkbox reads "Show only sections with issues (N)", where N is the total.
  - When it's on, sections with 0 issues are hidden, and inside the rubric only criteria below 100 are listed.
  - The choice persists per browser (`readPreference`/`writePreference`, key `evaluation.issuesOnly`).
  - With N = 0 the control reads "Nothing needs attention" and is disabled, and all sections show.
- [ ] **AC4 States.** Before judging (no scorecard), all counts are 0 and the control is disabled. With a scorecard it works as above. Layout holds at 375 px with no horizontal scroll, and nothing changes for runs whose data lack a field (missing arrays count 0).
- [ ] **AC5 Proof.** Checked in a browser on two real runs: Egypt `1e940baf` (issues) and one with few or no issues. Screenshots are inspected at 1440 and 375 px; the badge counts match the AC1 rules on the data; the toggle hides and shows sections; it survives a reload.

## Non-goals
- No backend or API change; no new issue types beyond AC1.
- No auto-opening or scrolling of sections (the user chose the filter, not the jump list).
- The Findings tab and the map are unchanged.

## Assumptions and open questions
- Assumption: "issue" = anything below full marks or flagged for review. A 92 on efficiency counts. If that feels noisy, a threshold is a follow-up. Owner: user; default: below 100.

## Plan
1. `api.ts`: `sectionIssues(view)` and `weakCriterion(c)`, with tests in `api.test.ts` (AC1).
2. `Controls.tsx`: `Disclosure` gains optional `badge?: number | "dot"`, rendered inside the title button with an aria-label (AC2).
3. `Evaluation.tsx`: compute the counts; a filter checkbox with the persisted preference; wrap each section in `show(id)`; filter rubric criteria; pass badges (AC2–AC4).
4. `workspace.css`: badge and filter styles, with the colour-safe palette; build the bundle.
5. Verify: tests, `tsc`, build, the browser probe at two widths on two runs (AC5); handoff.
