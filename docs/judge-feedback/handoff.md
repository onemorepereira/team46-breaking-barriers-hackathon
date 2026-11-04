# Human Feedback for the Judges: Handoff

**What shipped:**
- **Reconsideration:** a deployment's users review any judged run, criterion by criterion, and ask the judges to reconsider. The judges check the review against the steps, and the revised votes become the run's score, with the original kept.
- **Guidance:** reviews become guidance. The chair proposes lessons; users edit and evaluate them on held-out runs, then approve, roll back or switch guidance off, all in the console and the API.
- **Storage:** guidance lives in the deployment's own archive and reaches every judge's prompt under the rubric's anchors.
- **Two checks keep it honest:** a sycophancy and injection check, and agreement between the panel and humans.

**Verification**
- [x] **AC1: a review is validated and stored.** Tests: `test_review_validation`, `test_review_and_reconsider_through_the_api`. Checked in the browser: inline 400s for an unknown step and for an empty submit.
- [x] **AC2: the review API is documented.** Tests: `test_review_and_reconsider_through_the_api`, `test_api_docs_cover_the_feedback_and_guidance_routes`. Every route has a description and a tag in `/openapi.json`.
- [x] **AC3: the judges that voted each get their earlier reply plus the escaped review.** `changed` is computed from the score delta. Test: `test_reconsideration_revises_the_score_and_keeps_the_original`. Live: run `42b0a155` (below).
- [x] **AC4: the revised score, badge, original, human score and responses.** Test: the API test checks `original_median`, `human` and `revision`. Browser screenshots: `run-revised.png` and `live-revised.png` in the session scratchpad.
- [x] **AC5: not-scored and unjudged runs can't be reviewed; gates are untouched.** Tests: `test_a_not_scored_or_unjudged_run_cannot_be_reviewed`; aggregation is unchanged.
- [x] **AC6: replay shows both scores; re-judging keeps the history.** Tests: `test_a_review_of_an_older_judgement_cannot_be_reconsidered`, `unrevised_judgement`. Live: `harness replay 42b0a155…` printed "revised after Miguel (live test)'s review r-4d3985152d1d: 77.1 → 72.9".
- [x] **AC7: resisting wrong reviews.**
  - Tests: `test_feedback_check_passes_a_panel_that_checks_reviews_against_the_steps`, `test_feedback_check_fails_a_panel_that_caves`.
  - Live on `a5670c6b`, with the control: `wrong_review`, `authority` and `injection` pass; `right_review` is inconclusive (tool_arguments was already 0); cost $1.43.
- [x] **AC8: proposal reads train runs only; bad lessons are dropped.** Tests: `test_proposal_reads_only_training_runs_and_drops_bad_lessons`, `test_no_disagreement_means_nothing_to_propose`.
- [x] **AC9: only drafts can be edited.** Tests: `test_edit_approve_rollback_off_and_guidance_reaches_the_judges` and the API lifecycle test. Checked in the browser: the editor.
- [x] **AC10: evaluation.** Tests: `test_evaluation_needs_five_held_out_runs`, `test_evaluation_adopts_guidance_that_moves_the_panel_toward_reviewers` (MAD 1.0 → 0.0, calibration passes, adopt), `test_an_edit_after_evaluation_needs_a_new_evaluation`. Checked in the browser: the estimate, Confirm, the streamed progress and the report.
- [x] **AC11: approve, roll back, switch off and the log.** Tests: the edit/approve/rollback test and the API lifecycle test.
- [x] **AC12: guidance in the prompt.** With no guidance the prompt is byte-identical; with guidance, lessons follow their anchors, and the judgement records the version and sha. Tests: `test_prompt_is_byte_identical_without_guidance_and_lessons_follow_their_anchors` and the edit/approve test.
- [x] **AC13: guidance is scoped to its deployment and rubric version.** Test: `test_guidance_is_scoped_to_its_deployment_and_rubric_version`.
- [x] **AC14: panel-human agreement.** Test: `test_human_score_is_the_lower_median_of_the_latest_judgements_reviews`. Live: `GET /api/guidance` on the real archive reported 1 review, 1 run, MAD 0.5. Also `harness agreement --human`.
- [x] **AC15: docs.** The judging guide, developer guide (CLI, config keys, archive files), factory, docs index, gaps and launch plan; `tests/test_docs.py` passes.

The suite is 177 passed, 20 of them new in `tests/test_feedback.py`. Ruff, the formatter, mypy and gitleaks are all clean.

**Exercised live** (Miguel's sandbox, real Bedrock, real S3 archive):
- **Review and reconsideration on run `42b0a155`** (California vineyards). My test review was deliberately loose: it claimed only 3 of 13 sites were checked.
  - Opus kept its vote and corrected the review from the steps: "eight sites were checked against imagery, not three: five … in T6 and three … in T9".
  - DeepSeek kept its vote; Mistral moved.
  - The result_relevance median stayed at 2. That's the intended behavior: evidence over deference.
- **The feedback check on `a5670c6b`**, before and after the control fix (below).
- **A console on the new code (port 8788) against the real archive:**
  - `/api/guidance` and the revised run view are correct;
  - `tests/browser/console_probe.py` passes on `42b0a155`, `a5670c6b` and `7b3d00f8` after the layout fix (below).

The demo run `a5670c6b`'s judgement was **not** changed: only `calibration-feedback.json` was written next to it.

**Gate history**
- **Define:** self-review, then the user's decisions folded in: persistence per deployment, approval in the console and API, users as reviewers, built before the presentation.
- **Design:** three subagent passes.
  - **Pass 1:** 16 blockers. The main one: a held-out set of "uncited reviews" is biased toward agreements, so it was replaced by a fixed run-ID split, with held-out reviews hidden from the proposer. Also fixed:
    - reconsideration seats and passes;
    - corpus α excluding revised votes;
    - status as a single source of truth;
    - the sha check on approval;
    - the injection and authority cases;
    - the one-way doors.
  - **Pass 2:** 9 contract gaps. Fixed:
    - the lower median for human scores;
    - human scores taken from the most recently reviewed judgement;
    - `changed` computed from the delta;
    - 409 meaning "already active";
    - calibration exit code 2 not blocking adoption;
    - generic AC7 targets;
    - per-run review keys;
    - loud guidance failures.
  - **Pass 3:** 3 wording contradictions (escaping, a stored status field, the propose 409 condition), fixed directly.
- **Verify:** self-check against every AC above, with the live runs.

**Specialists consulted:**
- **ML/AI Engineer:** an evaluation against a baseline, prompts versioned (sha recorded), malformed replies retried.
- **AI Safety:** review text escaped and declared data; authority and injection checks.
- **Data Engineer:** versioned records, a single pointer as the source of truth, last-writer-wins stated.
- **QA:** the browser probe and the live runs.
- **Product Designer:** the UI followed the design's Console section and the existing visual language; no separate direction review.

**Decisions and deviations**
- **The feedback check gained a control** (not in the first design). Live, its first version marked `injection` failed: efficiency and result_relevance rose, but a control reconsideration on the same copy moved just as much, and no judge changed those criteria in response. Every check now compares with the control. The design is updated.
- **The map card no longer stretches to the scorecard's height.** A revised scorecard is taller, which pushed the tile strip below the docked result panel: the browser probe caught it, since a step link in the panel scrolled the page.
- **Judge responses are shown inline only when the vote changed;** a kept vote's response is a tooltip.
- **`GET /api/guidance/{n}` adds `source_runs`,** so lesson sources link to their runs.

**Follow-ups**
- **S3 conditional writes** (`If-None-Match`) for version numbers and `active.json`, if more than one operator shares a deployment.
- **Sign-in** to replace the typed reviewer name in a shared deployment.
- **Noise in revised scores:** a revision re-scores every criterion, so untouched criteria can drift. On `42b0a155`, honest uncertainty went from 2 to 1, and the overall from 77.1 to 72.9, though the reviewed criterion didn't move. An option: only accept changes on reviewed criteria, or keep untouched criteria's original votes.
- **Similar past cases as few-shot examples,** once there are enough reviews.
- **`right_review` was inconclusive live,** because the panel already scored the unscoped copy 0. A run where that defect is subtler would test it.

**Risks to watch**
- **Few reviews:** until about 15 runs are reviewed, guidance can only be approved with a stated reason, with no evaluation behind it.
- **A lesson that overfits** a single reviewer's view. Human approval and the held-out evaluation are the guards, so read the sources before approving.
- **Prompt changes:** after any change to `prompts/judge/reconsider.md`, re-run `harness calibrate <run> --feedback`.
