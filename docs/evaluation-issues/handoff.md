# Handoff: jump to problem areas in the Evaluation panel

Date: 2026-11-05. [Spec](spec.md).

## What changed
- **Counting:** `frontend/src/api.ts` gains `sectionIssues(view)` and `weakCriterion(c)`. They count issues per Evaluation section from data the run view already carries:
  - questions below 100;
  - unverified or contradicted conditions;
  - failed judges or low reliability;
  - gates, failure modes and tool errors;
  - missed reference sites;
  - licence blockers.
- **Badges:** `Disclosure` (`Controls.tsx`) gains `badge` (a count or a dot) and `hidden`.
- **Filter:** `Evaluation.tsx` shows a red count on each section with issues, and a dot on each rubric question below 100. A "Show only sections with issues (N)" checkbox hides clean sections and clean rubric questions, and it's remembered per browser (`evaluation.issuesOnly`). With no issues it reads "Nothing needs attention" and is disabled.
- **Styles:** in `workspace.css`, with the colour-safe palette.

## Design review
The user chose "Badges + filter" over a needs-attention list and issue chips. The built layout matches that preview.

## Proof (2026-11-05)
| AC | Proof |
|---|---|
| AC1 Counts | `api.test.ts` "evaluation issues: each section's rule, and an unjudged run counts nothing" (18/18 pass) |
| AC2 Badges | Browser, Egypt `1e940baf`: Rubric 4, Conditions 5, Licences 1; four rubric questions dotted (91.7, 83.3, 83.3, 75). DFW `195ff1d6`: Conditions 2, Licences 1, no rubric badge (all 100) |
| AC3 Filter | Browser: 13 sections become 3 (Egypt) and 2 (DFW); the rubric lists only weak questions; the setting survives a reload |
| AC4 States | Unjudged/zero case covered by the unit test (all 0, control disabled). 1440 and 375 px: no horizontal scroll, no console errors |
| AC5 Proof | The above, run against `harness ui` with real archived runs. Not exercised in a browser: a run with zero issues, because none exists locally; the unit test covers it |

Checks: frontend `tsc`, `npm test` 18/18, and `npm run build`. No backend change.

## Follow-ups
- If "below 100" feels noisy (e.g. efficiency at 92), add a threshold.

## Rollback
Revert the PR (frontend only).
