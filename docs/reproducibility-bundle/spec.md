# Reproducibility Bundle: One Export per Evaluation: Spec

**Roadmap:** R14 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none. R9 (ADB deployment profile) decides which config keys an ADB bundle redacts.
**Size:** about 3 days

## Problem
ADB needs to be able to repeat an evaluation, with the same method, in every country. The report says each evaluation should document its code, reference data and method (§4.2, requirement 7) **[ext]**. The organisers ask that every scored run keep its traces, inputs, and the rubric or reference it was judged against (V34) **[event]**.

Today the pieces are scattered, and some are missing:
- **What's in the run's archive:** the spans, the rubric snapshot, the guidance snapshot, the reference snapshot, and the visual and condition verdicts.
- **What sits elsewhere:** the guidance history is in the deployment's archive, and the config is in `harness.yaml`.
- **What isn't kept:** the judge prompt template, the agent's system-prompt text, the code version at judging time, and whether the code tree was dirty.

Replay also re-runs today's measured checks, so a replayed score can differ from the recorded one (docs/judging/guide.md:52). An analyst handed a run ID needs our repo, our S3 bucket and luck to say exactly how a score was produced. They can't prove it's the same method in Manila as in Nagoya **[team]**.

## Users
- **Primary:** ADB analysts and their reviewers, repeating or auditing an evaluation in another country.
- **Secondary:** the LGND/Ode benchmark team, and the team, archiving suites.

## Goals
- One file per evaluation, and one per suite, is enough to check its scores offline and to rerun it the same way.
- A verifier on a clean machine reproduces every recorded score, or says exactly what differs.
- A missing piece is named, never filled in silently.

## Non-goals
- **Reproducing the agent's behaviour.** A rerun calls live models and services, and gets a new trace. The bundle fixes the method, not the outcome.
- **Shipping a container image or the Python environment.** We record their versions only.
- **Imagery tiles by default.** They're large, and some are non-commercial.
- **Rewriting old archives.** Old runs are bundled with their gaps listed.

## User stories
- As an ADB analyst, I want one file I can open without AWS access that shows how a score was produced, so that I can defend it to a government.
- As a reviewer in a second country, I want to rerun the evaluation with the same rubric, panel, guidance, prompts and code, so that my results compare with the first country's.

## Acceptance criteria
- [ ] **AC1 Run bundle.** `harness bundle <run-id>` writes `out/bundles/<run-id>.zip`. It holds:
  - **`bundle.json`:** `schema_version`, `run_id`, `created_at`, the file list with each file's sha256, and the `gaps` list (AC4).
  - **`archive/`:** a copy of `runs/<id>/` without `tiles/`. That covers the spans, `run.json`, `result.json`, `summary.json`, `tool_results/`, `judgement.json` and `judgements/`, `conditions.json`, `visual.json` and the `visual/` images, `reference/`, and the R11 to R13 snapshots when present.
  - **`method/`:**
    - the rubric snapshot;
    - the guidance version, as `guidance_ref` records it;
    - the judge system prompt as rendered for this judgement;
    - the agent system-prompt text and its sha256;
    - the task prompt;
    - the area, conditions and visual-check prompts;
    - the effective config, redacted per AC6.
  - **`licences.json`:** the run's licence list and its presentable verdict.
  - **`REPEAT.txt`:** the exact commands to rerun: check out the commit, `uv sync --frozen`, set the config, `harness run`, `harness judge`.
- [ ] **AC2 Versions.** From this change on, `run.json` records the full 40-character commit and a `dirty` flag. `judgement.json` records the same at judging time, plus the sha256 of `uv.lock`. A bundle whose run or judgement was made from a dirty tree says "not reproducible from a commit" at the top of `REPEAT.txt`.
- [ ] **AC3 Verify.** `harness bundle verify <zip>` runs with no network, no AWS credentials and no `out/` index. It:
  1. checks every file's sha256;
  2. re-scores from `archive/` with the bundled rubric snapshot;
  3. prints the recorded and recomputed values for the overall score, every criterion and every reference metric.

  It exits 0 only when all of them are equal. When the verifier's matcher version differs from the judgement's `value_matcher_version`, it prints both and exits 2.
- [ ] **AC4 Gaps.** Each expected item that isn't available goes in `gaps` with a reason, such as "agent system-prompt text not archived before R14", and isn't written to `method/`. The verifier prints the gaps. A file taken from the current repo instead goes in `method/current/`, labelled "current repo version, not the one used".
- [ ] **AC5 Suite bundle.** `harness bundle --suite <suite-id>` writes `out/bundles/<suite-id>.zip`. It holds:
  - the suite file and `suite.json`;
  - one run bundle per archived run;
  - `compare.html`, `compare.csv` and `concepts.csv`, rebuilt from the bundled runs only.

  `verify` on it verifies each run and re-derives the CSVs byte for byte.
- [ ] **AC6 No secrets.** A bundle contains:
  - no AWS account IDs or ARNs;
  - no `archive_uri`, `lgnd_secret_id` or `runtime_arn` values (they're replaced by `<redacted>`);
  - no tokens.

  A test scans a bundle built from a fixture config holding a fake ARN and a 12-digit account ID, and finds neither.
- [ ] **AC7 Imagery.** `--with-imagery` adds the archived `tiles/`. Each image source then appears in `licences.json` with its attribution. A bundle holding any non-commercial item reads "check before sharing" in `REPEAT.txt`.
- [ ] **AC8 API.** `GET /api/runs/{id}/bundle` returns the same zip as the CLI. The run page in the workspace UI links to it. Every in-repo caller of the run API stays working.
- [ ] **AC9 Live proof.** Pecos run `79c18997` (or a fresher Pecos run) is bundled. Then `verify` passes in a fresh clone at the recorded commit, with no AWS credentials. The handoff records the bundle size and the verify output.

## Success signals
- **Metric (offline reproduction rate):**
  - **numerator:** bundles of runs judged after R14 ships on which `verify` exits 0 in a clean clone at the recorded commit;
  - **denominator:** all such bundles that are checked;
  - **target:** 100%.
- **Metric (gap rate):** bundles with at least one entry in `gaps` ÷ all bundles, reported separately for runs before and after R14. After R14, it should be 0.

## Constraints
- **The report** asks for documented code, reference data and method, with the same method across countries (§4.2, requirement 7). It also asks for sources and licences per evaluation (requirement 6) **[ext]**.
- **The organisers ask** for open and reproducible work by default (V33), with traces, inputs and the rubric or reference kept with each score (V34) **[event]**.
- **No credentials, account IDs or runtime data in the repo** (docs/factory.md, "Your own AWS sandbox").
- **Licences:**
  - Vantor Open Data is CC BY-NC 4.0 (`harness/sharp.py:51-56`), so imagery stays opt-in.
  - LGND Geo is a commercial product whitelisted for the event (T144) **[event]**. Its tool results are copied as archived, and their terms are an open question.

## What exists today
- **The archive layout:** `runs/<id>/` holds spans, `run.json`, `result.json` and `summary.json` (`analysis/trace.py:128-175`), plus `judgement.json` and `judgements/` (`harness/judge.py:400`, `:468-477`), `conditions.json` (`harness/conditions.py:69`), `visual.json` (`analysis/judging/visual.py:16`) and `reference/` (`harness/reference.py:48-71`).
- **The rubric snapshot, seats, matcher version and guidance snapshot** are in each judgement: `harness/judge.py:508-536`.
- **The judge prompt** is derived from the rubric and a template that isn't archived (`harness/judge.py:122-141`). The judgement keeps only an input hash (`:394`, `:448-453`).
- **The code version** is a short commit, with no dirty flag, recorded when the run starts (`harness/invoke.py:99-123`). For AgentCore runs, that's the harness's commit, not the deployed agent image's.
- **The agent system prompt** is archived only as a sha256 (`agent/handler.py:77-84`, `agent/telemetry.py:31`).
- **Replay** rebuilds the report from the archive (`harness/cli.py:86-99`). There's no `harness report` command; `replay` writes `out/<id>/report.html` (`harness/cli.py:42-51`). It uses the current measured checks (docs/judging/guide.md:52).
- **Compare outputs:** `harness/cli.py:102-133`. The licence list: `analysis/licences.py:201`.

## Assumptions and open questions
- **Assumption:** a run bundle without tiles stays small. The two local archives are 2.7 MB and 4.2 MB with tiles.
- **Open:** may archived LGND tool results be redistributed in a bundle? *Owner:* Miguel, who asks LGND. *Default:* yes for ADB and Clay, inside the evaluation, marked "LGND terms unknown" in `licences.json`.
- **Open:** should the agent's deployed image digest be recorded for AgentCore runs? *Owner:* team. *Default:* yes, when the runtime exposes it. Otherwise it goes in `gaps`.
- **Open:** which config keys does an ADB deployment redact? *Owner:* R9. *Default:* the three in AC6.
