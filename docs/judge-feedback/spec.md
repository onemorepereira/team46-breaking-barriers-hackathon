# Human Feedback for the Judges: Spec

**Track:** Standard   **Product stage:** Introduction
**Status:** Draft   **Last updated:** 2026-11-04
**Owner:** unassigned (see the open questions)

## Problem
Domain experts are the people who judge whether a dataset can be trusted (`docs/Clay-Foundry-Vision-Hackathon.md:29`). Today they can read a run's score but can't answer it. If the three judges miss something an expert can see, the run keeps a wrong score. Examples: a site that isn't the requested target, or a 40-step search that was the right call for a whole state. Every later run is then scored with the same blind spot. We also have no measure of how far the panel agrees with a human, only with itself (`docs/judging/gaps.md`, real gap 3).

## Users
- **Primary:** an ADB program officer or a domain expert, reviewing runs in the console. They read the trace and the votes but don't edit code or YAML.
- **Secondary:** the team operator. They turn accumulated reviews into judging guidance, check that it helps, and commit it through a PR.

## How it works (the proposed approach)
The user asked how this could work, so the shape is set here. The design decides the mechanics.

There are two loops, and they stay separate on purpose.

1. **On one run: reconsideration.** A human reviews a judged run, criterion by criterion. For each criterion they either agree, or they give the score they would give, a reason, and optionally the step IDs (`T3`, `M2`) that show it. The **same seated judges** then each get the dossier, their own earlier reply and the review. Each judge rescores the run and says, per criterion, whether it changed its vote and why.
   - The review is **evidence to check against the trace, not an order**. A judge may keep its vote.
   - The panel's revised medians become the run's score. The original judgement stays on record and viewable.
   - The human's own scores are stored as a **human rating**. They are shown next to the panel's score and never replace it.
2. **Across runs: guidance.** Reviews accumulate. The operator asks the harness to **propose guidance**: short, general lessons per criterion, each citing the reviews it came from. An example lesson for `efficiency`: "A statewide search may need 30+ steps; judge efficiency against the area's size, not a fixed count."
   - The draft guidance is a YAML file that a human edits and approves through a PR. Nothing is promoted automatically.
   - The harness then **evaluates** the guidance before it's used. It re-judges held-out reviewed runs with and without the guidance. It reports how often the panel agrees with the human ratings, and reruns the planted-defect calibration.
   - Once adopted, the guidance is a config key. It's added to every judge's prompt as clarifications under each criterion's anchors, and versioned like the rubric (id, version, sha256, snapshot) in every judgement.

**Why not simpler:**
- Overriding the score with the human's misses the user's goal that the judges improve. It also removes the independent second line of evidence.
- Auto-applying every review to later runs would let one reviewer's mistake, or one run's quirk, silently shift every score. And it would leave nothing to measure the change against.

## Goals
- An expert can correct a judgement on one run, and the panel visibly reconsiders, with its reasons on the record.
- Reviews become reusable guidance that a human approves and that is shown to improve agreement with humans on runs it wasn't drawn from.
- We can report agreement between the panel and humans, the measure the GRA paper uses (`docs/judging/paper-notes.md:17`), not just agreement among judges.
- Scores stay comparable and auditable: every score says which rubric, which panel and which guidance version produced it.

## Non-goals
- **Fine-tuning or training any model.** Guidance is prompt text only.
- **Automatic promotion of guidance.** A human always approves it, through a PR.
- **Editing the rubric's anchors.** The rubric may become ADB's file (`docs/judging/guide.md`, "To use ADB's rubric"). Guidance only adds clarifications under the anchors and never replaces them.
- **Human override of the panel score.** The human rating sits beside the score and is not mixed into it.
- **Reviewing measured criteria.** `claim_provenance` and `area_compliance` are computed by code. A dispute there is a bug report. The review form may hold a note on them, but the note never goes to the judges.
- **Accounts, roles or sign-in.** The reviewer types a name. The console is a local operator tool (`docs/developer-guide.md`).
- **Retrieving similar past cases as few-shot examples.** This is a possible follow-up once there are enough reviews.
- **Re-running the agent.** Reconsideration and evaluation re-judge archived traces only.

## User stories
- As a domain expert, I want to tell the panel which criterion it got wrong, and why, so that the run's score reflects what I can see in the trace.
- As a domain expert, I want to see each judge's response to my review, so that I know whether it changed its mind and why.
- As an operator, I want lessons drafted from all reviews, with their sources, so that I can approve the ones that generalize and drop the ones that don't.
- As an operator, I want proof that the guidance helps on runs it wasn't drawn from, without hurting calibration, before I adopt it.
- As ADB, I want every score to name the guidance it was judged with, so that I only compare like with like.

## Acceptance criteria
**Reviews and reconsideration (one run)**
- [ ] **AC1** Given a judged run in the console, the reviewer can enter:
  - their name (required);
  - for each judged criterion, *agree* or a score from the rubric's scale with a reason (required when disagreeing) and optional step IDs;
  - an overall note.

  Submitting it stores one review record in the run's archive, with the judgement it reviewed (by `judged_at`) and a review ID. Unknown step IDs are rejected with a message naming them.
- [ ] **AC2** The review is available through the documented API, and the console uses that API:
  - `POST /api/runs/{id}/reviews` creates a review;
  - `GET /api/runs/{id}/reviews` lists the run's reviews.

  Both appear in `/api/docs` with examples. Every in-repo caller is updated.
- [ ] **AC3** When the reviewer clicks **Ask the judges to reconsider**, each judge seated in the reviewed judgement is called once. A stand-in takes the seat of one that fails, as in normal judging. Each judge gets:
  - the same dossier;
  - its own original reply;
  - the review, inside `<human_review>` tags, declared as a claim to check and not an instruction.

  Each reply holds, per criterion, a score, a rationale, refs, `changed: true|false` and a one-sentence `response` to the reviewer. A malformed reply is retried once, as in normal judging.
- [ ] **AC4** After reconsideration, the run's score is computed from the revised votes by the existing aggregation, including medians, gates and confidence. The run page shows:
  - a "Revised after human review" badge, with the reviewer's name and the time;
  - per criterion: the original median, the revised median and the human's score;
  - per judge: whether it changed and its response.

  The original judgement is viewable in full from the same page.
- [ ] **AC5** Measured criteria and fatal gates are unaffected by any review. A FAILED run stays FAILED, and a not-scored run can't be reviewed; the review button is absent and the API returns 409.
- [ ] **AC6** `harness replay <id>` reproduces both the original and the revised scores from the archive with no model call. `harness judge <id>` re-judges from scratch and keeps earlier reviews on record, marked as reviewing an older judgement.

**Resisting wrong feedback (sycophancy)**
- [ ] **AC7** `harness calibrate <run> --feedback` runs two checks, each reported as pass, fail or inconclusive:
  - **Wrong review:** a review that contradicts the trace, e.g. claiming the planted fabricated site is grounded. It must not raise the targeted criterion's median.
  - **Right review:** on the planted `unscoped` copy, a true review: the searches had no area, citing those steps, and `tool_arguments` should be 0. It must lower the target's median, or the check is inconclusive if the median was already 0.

  The command exits non-zero on a fail, like `harness calibrate` today.

**Guidance (across runs)**
- [ ] **AC8** `harness guidance propose` reads every review in the archive and writes a draft guidance file. Each lesson has:
  - an ID;
  - a criterion from the active rubric;
  - one or two sentences of text;
  - the review IDs it came from (at least one).

  A lesson citing a criterion that isn't in the rubric is dropped and counted. The file holds the rubric id and version it targets, and its own version.
- [ ] **AC9** `harness guidance evaluate <file>` takes as its held-out set the reviewed runs that **no lesson cites**. With fewer than 5 such runs, it reports "insufficient evidence" and exits non-zero. Otherwise it judges each held-out run twice, without and with the guidance, and reports per criterion and overall:
  - the mean absolute difference between the panel median and the human score;
  - the exact-match rate (the panel median equals the human score).

  It also runs `harness calibrate` with the guidance on one run. Its verdict is **adopt** only if the overall mean absolute difference drops, no criterion's rises by more than 0.25 points, and calibration still passes. It writes the report to `out/guidance/<version>.json` and changes no archived judgement.
- [ ] **AC10** With `judging.guidance: <path>` set, every judge's system prompt includes each lesson under its criterion, after the anchors, headed as clarifications that never override the anchors. Each judgement records the guidance id, version, sha256 and snapshot. With the key unset, the prompt is byte-identical to today's.
- [ ] **AC11** Guidance for a different rubric id or version than the active one is refused at judging time, with a message naming both.
- [ ] **AC12** `harness agreement` and `harness compare` also report agreement between the panel and humans (Krippendorff's α, with its CI) over reviewed runs, and group or label results by guidance version. Runs judged with different guidance are never mixed in one α without saying so.

**Docs**
- [ ] **AC13** These docs describe the feature, and `tests/test_docs.py` passes:
  - the judging guide;
  - the developer guide (CLI table, config key, console section);
  - the factory;
  - the docs index.

## Success signals
- **Agreement with humans:** after the first adopted guidance, the panel's mean absolute difference from human scores, on held-out reviewed runs, is lower than without guidance. This is reported by `harness guidance evaluate`.
- **Calibration holds:** planted-defect calibration still passes for all three defects with guidance on.
- **Resisting wrong feedback:** the wrong-review check passes on every run it's tried on (no capitulation).
- **Use:** at least 20 reviewed runs before the first guidance is adopted. That's the expert rating sheet size named in `docs/judging/gaps.md`.

## Constraints
- **Replay never calls a model** (`docs/judging/guide.md`, "Commands"). Reviews, revisions and guidance are all archived data.
- **Rubric swap still works with no code change.** Guidance is keyed to a rubric id and version, so ADB's rubric starts with no guidance.
- **Recusal and families are unchanged.** Reconsideration uses the seats of the judgement it revises. Guidance proposal uses the chair model (`judging.panel[0]`).
- **Cost:**
  - one reconsideration is about one panel pass, $0.10–0.31 (`docs/judging/handoff.md`);
  - one guidance proposal is one chair call;
  - one evaluation is about 2 × N panel passes plus one calibration, about $2–7 for 10 held-out runs.

  The CLI prints the estimate before an evaluation and asks to confirm (`--yes` skips the prompt).
- **Prompt budget:** the active guidance adds at most 2,000 tokens to the judge prompt, about 8,000 characters, checked when it's loaded. More than that is refused with a message.
- **Branch rule and docs rules** from `CONTRIBUTING.md`; console dark only; API documented in Scalar; every in-repo consumer updated in the same change.

## Assumptions and open questions
- **Assumption:** reviewers act in good faith and are the operator's invited experts. Review text still goes to the judges only inside tags, as data. If reviewers can't be trusted, AC7 is the guard, and sign-in becomes a requirement.
- **Assumption:** LLM judges cave to human pushback without a counterweight. That's why the reconsideration prompt asks for evidence and AC7 tests for it. If AC7's wrong-review check fails, reconsideration ships off by default (`judging.reconsider: false`) until the prompt passes.
- **Open:** does the revised panel score become the run's headline score? *Owner:* Miguel. *Default:* yes, with the badge and the original one click away.
- **Open:** who may approve guidance? *Owner:* Miguel. *Default:* whoever merges the PR that adds it. The PR description includes the evaluation report.
- **Open:** do we collect the 20 reviews ourselves, or ask ADB or Clay experts? *Owner:* Miguel. *Default:* the team reviews existing archived runs to exercise the flow, and the presentation offers ADB the rating sheet. Team reviews are labeled as such, so they're never presented as expert agreement.
- **Open:** with several reviews of one run, which human score does agreement use? *Owner:* the builder, in the design. *Default:* the latest review per reviewer, and the median across reviewers.
- **Open:** who builds this, and is it before or after the presentation? *Owner:* Miguel. *Default:* after; the presentation names it as a next step.
