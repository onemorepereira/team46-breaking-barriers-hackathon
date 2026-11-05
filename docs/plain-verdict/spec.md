# Slice: Evals Explained in Plain Language

**Status:** Built (merged with prompt compliance in PR #7, 2026-11-04; the three-real-archive check, AC6, is not recorded; [handoff](handoff.md)) · **Owner:** Aditya · **Size:** about half a day · **Branch:** `slice/plain-verdict` from `main` · **Merges:** first (see [merge order](../factory.md#shipped))
**Read first:** [how a run is scored](../judging/guide.md), the [factory rules for slices](../factory.md#how-to-take-an-effort).

## Problem
A run's score page speaks to evaluators: criterion IDs, medians, "within one point", MAD, confidence reasons such as `fatal gate: no_answer`. An ADB program officer, or a hackathon judge, can't tell from it **what the agent found, whether to trust it, and what to check by hand**. Every fact needed is already in the run's archive. It just isn't said in plain words.

## What exists today (start here)
- **Judgement:** each run's `runs/<id>/judgement.json` is re-aggregated by `analysis.judging.panel.rescore(judgement, run)`, which returns a `PanelResult`: `overall`, `verdict` (`scored` / `FAILED`), `confidence`, `confidence_reasons`, per-criterion scores and votes, plus `failure_modes`. The judges' written rationales are in `run.judgement["passes"][i]["judges"][j]["rationales"]`, not in `PanelResult`.
- **Measured results:** `analysis.judging.measure.measure(run)` gives claims verified, claims inside the area, gates and the area label. `run.not_scored` marks an infrastructure failure.
- **Where scores are shown:** the console's run page (`harness/web/view.py:run_view` builds the JSON, `harness/web/static/app.js` renders it), and the static report (`analysis/report.py` and `analysis/templates/report.html`).
- **The rubric:** `rubrics/geo-dataset-v1.yaml` (the criteria's `question` text), loaded by `analysis/judging/rubric.py`.

## Acceptance criteria
- [x] **AC1 A plain summary per run.** A new pure function, `analysis/judging/explain.py:explain(run, result) -> dict`, returns:
  - `headline`, one sentence, e.g. "The agent found 8 likely solar parks in Jodhpur district; the judges trust this moderately.";
  - `summary`, at most 120 words, answering: what was asked; what was found (how many, and where); how much to trust it (the score and the confidence, in words); and the one to three biggest reasons for doubt (lowest-scoring criteria, majority failure modes, gates);
  - `check_by_hand`, a list of one to three concrete things a person should verify, e.g. "Look at the 3 results the imagery check couldn't confirm.", built from the real imagery-check verdicts in the trace.

  It is built only from the archive and the `PanelResult`. **No new model calls.**
- [x] **AC2 Every state reads correctly.** A scored High run, a scored Medium run, FAILED with no answer, FAILED with no successful tool call, **not scored** (infrastructure), and a run that was never judged each get an accurate summary. "Not judged" says how to judge it. Tests build each state with `tests/fixtures/builder.py` and assert the key facts (counts, the score, the reason).
- [x] **AC3 No jargon.** A test fails if any `headline`, `summary` or `check_by_hand` text contains any of these terms: `criterion`, `rubric`, `median`, `MAD`, `α`, `alpha`, `dossier`, `provenance`, `gate`, `span`, `T1`–`T99` refs, or snake_case IDs. Plain words replace them: "the judges", "checked against the tool's own output", "inside the area you asked for".
- [x] **AC4 Each criterion has a plain name.** The rubric gains an optional `plain:` line per criterion (e.g. `result_relevance` → "Are the results actually what was asked for?"). The loader (`rubric.py`) accepts it.
  - **Lookup:** each run's scorecard is built from the rubric *snapshot* archived in its judgement, which has no `plain:` lines for existing runs. So look plain lines up by criterion ID in the **current** rubric (`judging.rubric` in `harness.yaml`), then fall back to the snapshot's `question`.
  - **Display:** the scorecard shows the plain line under each criterion name, for old and new runs alike (test both).
- [ ] **AC5 Shown where people look.** On the run page, a "What this means" card sits above the scorecard (headline, summary, a check-by-hand list). It's also at the top of the static report. The run JSON carries it as `run_view(...)["explanation"]`. The existing tests and `tests/browser/console_probe.py` still pass.
- [ ] **AC6 Readable.** The summaries of 3 real archived runs, pasted in `handoff.md`, were read by someone outside the team, or scored by a readability check at grade 9 or below (e.g. Flesch-Kincaid via `textstat`, dev-only, not a runtime dependency).

## Non-goals and boundaries
- No change to how runs are **scored**: no rubric weights, judge prompts or aggregation.
- No new LLM calls. That keeps this cheap, deterministic and replayable. An LLM-written summary could be a later slice.
- Don't touch `agent/`, `tools/` or `infra/`.

## How to check your work
```sh
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run harness ui        # open a few archived runs at http://127.0.0.1:8787/runs
uv run harness replay <run-id> && open out/<run-id>/report.html
uv run --no-project --with playwright python tests/browser/console_probe.py <your-run-id>
```

## When done
Write `docs/plain-verdict/handoff.md` (what shipped, each AC with its proof, the three sample summaries), set this file's Status to `Built`, update this slice's row in [the factory](../factory.md), and open a PR to `main`.

## Local review note — 2026-11-04

AC5 is implemented and checked in the API, static report and browser on a clearly labeled synthetic archive. The repository browser probe and AC6 still need real archived runs; the supplied HTML report alone does not contain the full source archive. Do not call these checks complete or the slice merged until the handoff has those results.
