# The Factory: Every Effort, Its Purpose and Status

The ledger of work on the Team Foundry eval harness: every spec-to-handoff effort, the changes made without a spec, and what is still open. Each effort follows the same path: **spec** (problem and testable acceptance criteria), then **design** (options, failure modes, rollback), then **build**, then **verify** (each criterion proven by something that ran, recorded in the **handoff**). Small efforts skip the design. Update this page when an effort starts, changes status or ships (see [CONTRIBUTING](../CONTRIBUTING.md#documentation-conventions)).

**Status key:** **Shipped**: built, verified and merged. **In progress**: being built or verified. **Open**: decided but not started. **Blocked**: waiting on someone outside the team. **Not taken**: specified, but nobody built it.

## Efforts with a spec

| # | Effort | Purpose | Track | Status | ACs proven | Records |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Eval harness** (2026-11-03) | Run an agent on AgentCore with RODA and LGND Geo, capture every model and tool decision as OpenTelemetry spans in an S3 archive, check the trace, grade claim provenance, report, replay, compare | Standard | Shipped | 11/11 | [spec](eval-harness/spec.md) · [design](eval-harness/design.md) · [spikes](eval-harness/spikes.md) · [handoff](eval-harness/handoff.md) |
| 2 | **Layering** (2026-11-04) | Separate `core` / `tools` / `agent` / `analysis` / `harness`, with prompts as files and tool knowledge in `tools/`, enforced by tests | Quick | Shipped | 4/4 | [spec](layering/spec.md) · [handoff](layering/handoff.md) |
| 3 | **Judging and console** (2026-11-04) | Score each run's workflow and output against a generalized rubric with a cross-family judge panel, with agreement, confidence and calibration. The Team Foundry console (FastAPI) to run, watch and score | Standard | Shipped (PR #1). Since revised: a [tribunal of three](judging/handoff.md) (Opus, DeepSeek, Kimi, with reserves), and each criterion scored by the mean of every vote over three concurrent passes ([judging stability](judging-stability/handoff.md), PR #17) | 15/15 | [spec](judging/spec.md) · [design](judging/design.md) · [guide](judging/guide.md) · [gaps](judging/gaps.md) · [paper notes](judging/paper-notes.md) · [handoff](judging/handoff.md) |
| 4 | **Example cards** (2026-11-04) | One-click example prompts for every continent, Asia first, mostly in ADB developing member countries, each with a verified official boundary | Quick | Shipped | 8/8 | [spec](example-cards/spec.md) · [handoff](example-cards/handoff.md) |
| 5 | **Tile cache** (2026-11-04) | Archive each run's result tiles so archived runs replay their imagery offline; serve basemaps and tiles from a disk cache | Standard | Shipped | 10/10 | [spec](tile-cache/spec.md) · [design](tile-cache/design.md) · [launch](tile-cache/launch.md) · [handoff](tile-cache/handoff.md) |
| 6 | **Docs pass** (2026-11-04) | Documentation in ship shape: an accuracy audit against the code, the developer guide, CONTRIBUTING, the docs index, this ledger, and a test that keeps the links and references true | Quick | Shipped | 5/5 | [spec](docs-pass/spec.md) · [handoff](docs-pass/handoff.md) |
| 7 | **Console polish** (2026-11-04) | Dark theme across the console, report and API docs; a docked result panel instead of clipped popups; step links that scroll the timeline, not the page; the area-narrowing fix and the LGND token refresh behind run `fdacf7cf` | Standard | Shipped | 8/8 | [spec](console-polish/spec.md) · [design](console-polish/design.md) · [handoff](console-polish/handoff.md) |
| 8 | **Judge feedback** (2026-11-04) | A human reviews a judged run; the same judges reconsider with the review as evidence, not an order. Reviews are distilled into guidance that users approve in the console and that is stored in the deployment's own archive, after evaluation on held-out runs. This adds panel–human agreement (gap 3) | Standard | Shipped (PR #5) | 15/15 | [spec](judge-feedback/spec.md) · [design](judge-feedback/design.md) · [launch](judge-feedback/launch.md) · [handoff](judge-feedback/handoff.md) |
| 9 | **AWS hardening** (2026-11-04) | Bring the stack to AWS's documented practice: a conditioned trust policy, logs and metrics scoped like AgentCore's documented execution role, open-data S3 reads limited to other accounts' buckets, a versioned and access-logged archive, 30-day runtime logs, and a non-root, pinned, scanned container | Quick | Shipped (PR #8; deployed 2026-11-04) | 7/7 | [spec](aws-hardening/spec.md) · [handoff](aws-hardening/handoff.md) |
| 10 | **ADB alignment** (2026-11-04) | Line results up with the LGND/Ode benchmark for ADB: reference sets with recall, precision, count ratio and lift under its matching rule; data and licences per run, and whether a result is presentable; per-concept and transfer reporting; a T1 suite over its concepts and places | Standard | Shipped (PR #9) | 10/10 | [what the report means for us](adb-alignment/lgnd-ode-brief.md) · [spec](adb-alignment/spec.md) · [design](adb-alignment/design.md) · [handoff](adb-alignment/handoff.md) |

## Slices open for the team (2026-11-04)

Four self-contained slices, one per person, opened on 2026-11-04. Three have shipped and one was not taken (status below, 2026-11-05). Each spec says what exists, the testable acceptance criteria, what not to touch, and how to check the work, so you can hand it to Kiro or your tool of choice as is. Take one, put your name in its Owner line and in the table below, and follow "How to take a slice".

| Slice | Purpose | Size | Status | Owner | Spec |
| --- | --- | --- | --- | --- | --- |
| **Evals in plain language** | A plain summary on every run ("what was found, how much to trust it, what to check by hand"), built from the archive with no new model calls | about half a day | Shipped (merged with prompt compliance in PR #7, 2026-11-04). The three-real-archive readability check (AC6) is not recorded | Aditya | [spec](plain-verdict/spec.md) · [handoff](plain-verdict/handoff.md) |
| **Prompt compliance** | Check each result against **every** condition in the prompt (e.g. "within 10 miles of a protected area, inside ZIP 75082") and show evidence or its absence, per claim | about a day (splits in two) | Shipped (PR #7, 2026-11-04; rubric v2). Live ZIP run `d0bfb674` checked; planted-defect calibration under rubric v2 not recorded | Aditya | [spec](prompt-compliance/spec.md) · [handoff](prompt-compliance/handoff.md) |
| **Visual design** | Make the console read as a designed product on a projector: type, spacing, hierarchy, a matching report; visual only, behavior unchanged | about a day | Not taken. The Foundry [workspace UI](workspace/README.md) (PRs #12–#13, refined through PR #36) became the presented interface instead | — | [spec](visual-design/spec.md) |
| **Presentation** | An interactive HTML deck (11 slides), a live demo of **judging** an already-built run, a one-pager for ADB, and Q&A prep; every number sourced to the repo | about a day | Shipped (PR #3; slides added in PRs #6, #10 and #11; a 5-minute deck in PR #16). Rehearsal (AC6) not logged | Miguel | [spec](presentation/spec.md) · [handoff](presentation/handoff.md) |

**Starting point:** `main` holds everything: `design/eval-harness` was merged in PR #1 on 2026-11-04 and is retired. Branch from `main`.

**Who owns what, and the merge order:** the slices touch some of the same files, so they merge in this order, each rebasing on `main` before its PR:
1. **Plain language** merges first, as the smallest change. It adds `analysis/judging/explain.py`, the optional `plain:` line in the rubric (with its loader support in `rubric.py`), `run_view(...)["explanation"]`, and one card in `run.html`, `app.js` and `report.html`.
2. **Prompt compliance** merges second. It owns `analysis/judging/measure.py`, `dossier.py`, `harness/area.py`, `core/geometry.py`, and the rubric's new criterion and version bump. It rebases on plain language's rubric and `rubric.py` changes.
3. **Visual design** merges last, because it restyles the pages the other two add cards to. Until then, style by class names (new cards use Tabler `card` markup), and rebase and restyle the new cards before merging.
4. **Presentation** changes no code, and freezes its deck at the time set in its spec.

### Your own AWS sandbox
Each teammate works in **their own sandbox account**. The committed `harness.yaml` points at Miguel's (892605951158), so you override its account-specific settings in a personal file. **Never edit or commit `harness.yaml` for your sandbox.**
1. Deploy the stack into your account: `cd infra && CDK_DOCKER=podman npx aws-cdk deploy` (see the [developer guide](developer-guide.md)). Note its outputs: `ArchiveUri`, `LgndSecretArn` and `RuntimeArn`.
2. Create `harness.local.yaml` next to `harness.yaml`. It's git-ignored (`*.local.yaml`), and the harness reads it on top of `harness.yaml` automatically:
   ```yaml
   archive_uri: s3://<your ArchiveUri bucket>
   lgnd_secret_id: <your LgndSecretArn>
   runtime_arn: <your RuntimeArn>
   ```
3. Log in to LGND Geo once, into **your** secret: `uv run harness lgnd-login`.
4. Check before you push that `git status` doesn't list `harness.yaml`. If it does, `git restore harness.yaml`.

**Runtime data is never committed.** Runs, archives, reports and tiles (`archive/`, `out/`) stay on your machine and in your own S3 bucket, and git ignores them. Everyone works with runs they made themselves.

### How to take a slice
1. **Set up:** follow the [developer guide](developer-guide.md) (`uv sync`; `uv run pytest` passes offline). For anything live, set up [your own AWS sandbox](#your-own-aws-sandbox), and keep its temporary credentials in your shell (they expire every few hours).
2. **Branch:** `git switch -c slice/<name> main`. Never commit to `main` directly, and never commit credentials.
3. **Get runs to look at:** a fresh clone has no runs, because runtime data is never committed. Make a few with `uv run harness ui` and the example cards, or `uv run harness run --prompt prompts/tasks/dallas-dc.md --model sonnet --backend local`. Each costs about $0.20–1.00 in Bedrock and takes 1–7 minutes. Don't restart the console while one of your runs is going, or the run dies.
4. **Build to the spec:** keep to its non-goals, and if the spec is wrong or unclear, fix the spec first and say so in the PR. Run the checks it lists, plus `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`. The browser probe needs a run that exists on your machine: `uv run --no-project --with playwright python tests/browser/console_probe.py <your-run-id>`.
5. **Finish:**
   - write `docs/<slice>/handoff.md`: what shipped, and each acceptance criterion with what proved it (a test name, a command, a screenshot, a run ID);
   - set the spec's Status to `Built`;
   - update the slice's row here;
   - open a PR to `main`, and ask a teammate who didn't build it to review it.

## Efforts recorded with a handoff

All merged to `main`; dates are GitHub merge dates (UTC).

| Effort | Purpose | Status | Owner | Records |
| --- | --- | --- | --- | --- |
| Value matching | Reject opposite verdicts, coordinates spliced across records, and failed tool output; label older replays | Shipped (PR #7, 2026-11-04; matcher version 3) | Aditya | [spec](value-matching/spec.md) · [handoff](value-matching/handoff.md) |
| Foundry workspace UI | The supplied Foundry React UI at `/workspace/`, connected to the live evaluation backend, then reworked for usability, summaries and quick score feedback | Shipped (PR #12 and its review fixes in PR #13, 2026-11-04; PR #15, 2026-11-05) | Aditya (review fixes: Miguel) | [README](workspace/README.md) · [review fixes](workspace/review-fixes.md) |
| Workspace map popups | Imagery on the workspace map with its details; open archived runs in about 2 s instead of 6–15 s | Shipped (PR #14, 2026-11-05). The popups were later replaced by an imagery inspector beside the map (PR #15) | Miguel | [handoff](workspace-map-popups/handoff.md) |
| Judging stability and workspace review | Scores that settle rather than flip, judging in about 20 s, per-question human review in the workspace, a result panel on the map, and a design pass | Shipped (PR #17, 2026-11-05, ported into PR #15's workspace) | Miguel | [handoff](judging-stability/handoff.md) |
| Observed scenes | Result tiles show the scene LGND matched (sensor, date, place), not a basemap mosaic | Shipped (PR #30, 2026-11-05) | Miguel | [handoff](observed-scenes/handoff.md) |
| Visual check | Each reported site is looked at in the sharpest open image (Vantor, OpenAerialMap, NAIP, Sentinel-2) by a vision model, and scored as `visual_confirmation` | Shipped (PR #33, 2026-11-05; rubric v3) | Miguel | [spec](visual-check/spec.md) · [design](visual-check/design.md) · [launch](visual-check/launch.md) · [handoff](visual-check/handoff.md) |
| Evaluation issue filter | Red issue counts on Evaluation sections and a filter to show only sections with issues | Shipped (PR #34, 2026-11-05) | Miguel | [spec](evaluation-issues/spec.md) · [handoff](evaluation-issues/handoff.md) |
| Map fit | Runs open and finish framed on the searched area's main part and the evidence, not on far-flung islands | Shipped (PR #35, 2026-11-05) | Miguel | [spec](map-fit/spec.md) · [handoff](map-fit/handoff.md) |

## Changes without a spec

Fixes and small features, each recorded in its commit or PR. On 2026-11-04 unless the row says otherwise.

| Change | Why | Commit |
| --- | --- | --- |
| Runs whose model calls all failed are **not scored**, not FAILED | An expired-credentials run was scored FAILED 0, and judging cost $0.06 | `5f3c15c` |
| Judge **tribunal of three**, with reserves that stand in for a failed judge | The user's call: three judges, dropping the most problematic. Grok was slowest and was the only one to error | `74d434d`, `08401ae` |
| The report renders the answer as **Markdown** | It showed raw `**` and `\|---\|` next to formatted sections | `e4ef776` |
| **Area lookup** only accepts boundaries and places; enforcement keeps a narrower area | "Northern California" resolved to a 20 m building, and a run hit the 40-step limit | `c041b6f` |
| Runs list from **saved rows**; documented API at `/api/docs` (Swagger, later replaced by Scalar in console polish) | The runs list took about 7 s (S3 re-reads); the API docs were bare | `07d197c` |
| Runs API **cursor paging** and filters; every API consumer updated | Paging asked for; consumers audited | `bd2ae60`, `bd2970a` |
| **Team slices**: four self-contained specs, plus how to take a slice and the merge order | The team works in parallel on the day before the presentation | `b3d5520` |
| **`harness.local.yaml`**: a git-ignored override merged over `harness.yaml` | Teammates work in their own AWS sandboxes without editing the shared config | `ec7ea92` |
| **Branch rule**: every change goes on a `feature/`, `doc/`, `chore/` or `slice/` branch from `main`, through a PR | `main` is the shared baseline | PRs #1–#3 |
| **Workspace live panel** animates while the agent and judges work, and fits without scrolling (2026-11-05) | The live trail needed scrolling and looked idle while judges worked | PRs #20, #25 |
| **Workspace layout fixes**: Team Foundry mark and favicon; the build hotfix; the docked tile panel and phone layout; no header Evaluation button; imagery on first view in a full-height slide-out tile panel; a picked thumbnail opens at its title (2026-11-05) | Review of the merged workspace | PRs #19, #22, #23, #24, #26, #28 |
| **Map credit and legend**: the imagery credit stays folded unless hovered or focused, is compact at every width, and the legend stops short of it (2026-11-05) | The legend and the attribution overlapped | PRs #21, #29, #31 |
| **Agent image installs `libexpat1`** (2026-11-05) | `rasterio`, added for observed scenes, didn't load in the agent image without it | PR #32 |
| **Every inspector image shows its source pill**, and a cached image no longer sticks on "Fetching" (2026-11-05) | Only some images named their source | PR #36 |

## Open work

| Item | Purpose | Status | Owner and default |
| --- | --- | --- | --- |
| **ADB's rubric and task** | Score against ADB's own criteria, not our generalized rubric | Blocked on Clay (V191) | Clay. Default: `rubrics/geo-dataset-v1.yaml`; ADB's drops in as YAML |
| **Answer key** for outcome correctness | Judge whether found sites are real, not just traceable, e.g. solar farms against USPVDB, with a measured recall and precision criterion | Partly done: reference sets give recall and precision beside the score ([ADB alignment](adb-alignment/handoff.md), PR #9), with one set so far (`references/uspvdb-tx-pecos-v4`); not a scored criterion | Team. See [gaps](judging/gaps.md) |
| **Human-expert ratings** of about 20 runs | Validate the panel against experts, as the GRA paper did (expert α ≈ 0.56) | Open | Team |
| **A gate for unconfirmed results** | A run whose imagery checks confirm no candidate still scores about 96 and High | Partly addressed 2026-11-05: the [visual check](visual-check/handoff.md) scores `visual_confirmation`, so a site seen absent lowers the score (Abilene wind 96.2 → 89.4). There's no gate on the score or the confidence | Team |
| **AgentCore redeploy** | The agent-side fixes (area narrowing, LGND token refresh) reach AgentCore runs only after a redeploy | **Done** 2026-11-04 (run `a5670c6b` used them; [console-polish handoff](console-polish/handoff.md)) | Redeploy after any change to `agent/`, `tools/` or `prompts/agent/` |
| **Tile backfill** for older runs | Archive result tiles for runs made before the tile cache | Open (2 runs done) | Team: the loop in [tile-cache launch](tile-cache/launch.md) |
| **Unrun example cards** | 15 of the 16 cards have verified areas but no full run | Open | Team: reword or drop a card whose feature LGND can't find |
| Harness follow-ups | A long synchronous AgentCore call (spike S2), the OSM answer-key count (S6), the token cap for country-scale prompts | Open | See the [eval-harness](eval-harness/handoff.md) and [layering](layering/handoff.md) handoffs |
| Visual-check follow-ups | Sites given as separate latitude and longitude claims get no check; one vote per site (a second checker from another family); image dates not compared with the asset | Open | See the [visual-check handoff](visual-check/handoff.md#known-limits-and-follow-ups) |
