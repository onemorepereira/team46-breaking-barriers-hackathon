# Handoff: judging stability, speed, and per-question review in the workspace

Date: 2026-11-04. Records only; [How a run is scored](../judging/guide.md) describes the present.

## Problems, with evidence
- **Scores flipped on identical evidence.** The Jodhpur run (`36efccf9`) was judged four times without anything changing, and scored 83.3, 93.8, 87.5 and 93.8.
  - Across 18 single passes of that run, one pass's median score ranged from 75 to 100 (sd 6.9).
  - A median of three votes on a 0–2 scale moves a criterion by 50 points when one vote flips.
- **"Temperature 0" was not true for most judges.** Bedrock rejects `temperature` for Opus 5.5, Sonnet 5.5, Kimi K3 and Grok 4.7; this was checked live on 2026-11-04. The judge silently retried without it, so those judges sampled at the model's default.
  - DeepSeek V3.2, Mistral Large 3 and Qwen3 accept it.
  - Even at temperature 0, DeepSeek and Mistral changed votes between identical calls.
- **Judging took 40–110 s.** Mistral and DeepSeek answer in about 10 s. Kimi K3 reasons at length by default: it took 34–38 s on the recorded judgements, 109 s in one probe, and cost 11× the others ($0.105 against about $0.009).
- **No per-run review in the workspace.** The review form was one dropdown under the final answer, with no judge votes or reasons beside it, and saved reviews showed as raw JSON.

## What changed
**Judging** (`harness/judge.py`, `harness.yaml`):
- **Three passes,** run concurrently: no extra wall time.
- **Re-judging adds votes.** A re-judge whose inputs hash the same (`inputs_sha`: system prompt with guidance, dossier, seated panel) adds its passes to the recorded ones, keeping the newest `MAX_PASSES` = 9. A change to the evidence, guidance or panel starts afresh, and so does a reconsideration.
- **Straggler cut.** With two passes complete, any pass still running `STRAGGLER_S` = 25 s after judging began is left out, and the judgement records `dropped_slow_passes`.
- **Kimi effort.** `judge_request_fields: {reasoning: {effort: low}}` for Kimi as a judge; its agent runs are unchanged.
  - Measured on the Jodhpur dossier: about 5 s alone and 6–17 s with three passes in parallel.
  - At medium effort, three concurrent calls took 25–52 s.
- **Sampling recorded.** Each judge records the `temperature` it actually ran at (`None` means the model's default). Models that reject temperature are remembered for the process, so the failing call isn't repeated.

**Scorecard view** (`harness/web/view.py`):
- `votes_all`: every judge's vote on every criterion, across all passes.
- `pass_count` and `overall_range`: the lowest and highest single-pass score.
- `overall_se`: the standard error of the headline.
- `passes_dropped`, and per-judge `temperature`.

**Workspace** (`frontend/src`):
- **Evaluation: review each question.** Every rubric question shows each judge's votes from every pass as coloured marks. Opening it shows the anchors, each judge's rationale and cited steps, and *Agree* or *Suggest a different score* (a score from the anchors, a reason, and optional steps).
  - A sticky bar collects the drafts into one review: name (remembered in the browser), an optional note, and Save. It posts to the existing `POST /api/runs/{id}/reviews` (`draftPayload` in `api.ts`).
  - Saved reviews render as readable lines, each with *Ask the judges to reconsider*.
  - Findings links to it ("Do you agree with the judges?").
- **Score:** the hero shows passes, votes per question, ± standard error and the single-pass range. Scores have one format everywhere (87.5, not "88" beside "87.5").
- **Result panel on the map:** clicking a location, an imagery dot or footprint, or a thumbnail opens a panel docked inside the map's right edge, a bottom sheet on phones. It shows the tile and its details, and closes with × or Esc.
  - It replaces the popup, which covered the prompt card.
  - While it's open it owns the right edge: the basemap switch and zoom buttons hide, and the attribution stays visible.
- **Design pass:**
  - The unlabelled "i" button, the duplicate Evaluation button and the idle status pill are gone; About moves to the footer.
  - The map legend matches the marks (area, numbered location, imagery dot, outside), and the redundant "Saved search area" overlay is removed.
  - No font below 11 px (176 declarations raised).
  - On phones: the navigation is visible, the map sits above the panel, and tapping a location scrolls to the map. The prototype stylesheet hid both below 800 px.
  - Reported locations named "(s2/obs:…)" now find their imagery.

## Proof
**Stability**, from back-to-back judgings of the same evidence (Jodhpur):

| Judging | Before (one pass) | Three passes, Kimi medium | Three passes, Kimi low |
|---|---|---|---|
| 1st | 83.3 | 86.1 | 89.6 |
| 2nd | 93.8 | 87.8 (6 passes) | 88.5 (6) |
| 3rd | 87.5 | 87.0 (9 passes) | 88.3 (8, 1 dropped) |

**Speed** (`harness judge` path, local archive copy): 13.5 s and 20.0 s, plus one 54 s judging under the earlier 15-s-after-the-second-pass rule. That 54 s is why the budget now counts from the start. From the UI on S3, before the Kimi change: 50 s and 58 s.

**Cost:** about $0.22 per three-pass judging on a Sonnet run (Mistral, DeepSeek, Kimi), up from about $0.12–0.17 for one pass.

**Aggregation rules compared** (bootstrap of the 18 recorded passes, 3 passes per sample):

| Rule | sd | Range |
|---|---|---|
| Mean of pass medians (unchanged) | 3.7 | 77–98 |
| Mean of all votes | 2.3 | 81–94 |

**Adopted 2026-11-04 (user's call):** the score is now the mean of all votes. The median is still recorded for review comparisons.

**Tests and checks:**
- `tests/test_judging.py::test_rejudging_unchanged_inputs_adds_passes_and_new_inputs_start_afresh`
- `tests/test_judging.py::test_a_straggling_pass_is_left_out_once_two_are_complete`
- `frontend/src/api.test.ts`: the multi-question review payload, the score format, the chip match
- Every CI check passes: ruff, mypy, pytest, the frontend tests and build.

**Browser** (headless Chromium, desktop 1440×900 and phone 390×844, local-archive console):
- the panel opens from a list row and closes with Esc;
- the review draft (Suggest → score → reason) shows in the sticky bar;
- the phone layout shows navigation, map, then panel.

A review was **not** saved into the live deployment from the browser; the endpoint is unchanged and covered by `tests/test_feedback.py`.

## Open
- **Mean of all votes:** adopted. One outlier judge now moves a criterion by a third of its vote, where under the median it moved nothing; recusal and three families limit that.
- **Kimi at low effort** is a quality trade for speed. Its votes stayed within the panel's spread on Jodhpur. Calibration (`harness calibrate`) has not been rerun with it.
- The S3 credentials expired during verification. The live-console check of the latest build ran against a local copy of the archive.

## Rollback
Revert the PR.
- Judgements written with several passes stay readable by the old code: the passes field is unchanged, and the old code reads pass 1 for display.
- Setting `judging.passes: 1` and removing `judge_request_fields` restores the old judging alone.
