# The Factory: Every Effort, Its Purpose and Status

The ledger of work on the Team Foundry eval harness: every spec-to-handoff effort, the changes made without a spec, and what is still open. Each effort follows the same path: **spec** (problem and testable acceptance criteria), then **design** (options, failure modes, rollback), then **build**, then **verify** (each criterion proven by something that ran, recorded in the **handoff**). Small efforts skip the design. Update this page when an effort starts, changes status or ships (see [CONTRIBUTING](../CONTRIBUTING.md#documentation-conventions)).

**Status key:** **Shipped**: built, verified and merged. **In progress**: being built or verified. **Open**: decided but not started. **Blocked**: waiting on someone outside the team.

## Efforts with a spec

| # | Effort | Purpose | Track | Status | ACs proven | Records |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Eval harness** (2026-11-03) | Run an agent on AgentCore with RODA and LGND Geo, capture every model and tool decision as OpenTelemetry spans in an S3 archive, check the trace, grade claim provenance, report, replay, compare | Standard | Shipped | 11/11 | [spec](eval-harness/spec.md) · [design](eval-harness/design.md) · [spikes](eval-harness/spikes.md) · [handoff](eval-harness/handoff.md) |
| 2 | **Layering** (2026-11-04) | Separate `core` / `tools` / `agent` / `analysis` / `harness`, with prompts as files and tool knowledge in `tools/`, enforced by tests | Quick | Shipped | 4/4 | [spec](layering/spec.md) · [handoff](layering/handoff.md) |
| 3 | **Judging and console** (2026-11-04) | Score each run's workflow and output against a generalized rubric with a cross-family judge panel, with agreement, confidence and calibration. The Team Foundry console (FastAPI) to run, watch and score | Standard | Shipped (panel revised: [tribunal of three](judging/handoff.md)) | 15/15 | [spec](judging/spec.md) · [design](judging/design.md) · [guide](judging/guide.md) · [gaps](judging/gaps.md) · [paper notes](judging/paper-notes.md) · [handoff](judging/handoff.md) |
| 4 | **Example cards** (2026-11-04) | One-click example prompts for every continent, Asia first, mostly in ADB developing member countries, each with a verified official boundary | Quick | Shipped | 8/8 | [spec](example-cards/spec.md) · [handoff](example-cards/handoff.md) |
| 5 | **Tile cache** (2026-11-04) | Archive each run's result tiles so archived runs replay their imagery offline; serve basemaps and tiles from a disk cache | Standard | Shipped | 10/10 | [spec](tile-cache/spec.md) · [design](tile-cache/design.md) · [launch](tile-cache/launch.md) · [handoff](tile-cache/handoff.md) |
| 6 | **Docs pass** (2026-11-04) | Documentation in ship shape: an accuracy audit against the code, the developer guide, CONTRIBUTING, the docs index, this ledger, and a test that keeps the links and references true | Quick | Shipped | 5/5 | [spec](docs-pass/spec.md) · [handoff](docs-pass/handoff.md) |
| 7 | **Console polish** (2026-11-04) | Dark theme across the console, report and API docs; a docked result panel instead of clipped popups; step links that scroll the timeline, not the page; the area-narrowing fix and the LGND token refresh behind run `fdacf7cf` | Standard | Shipped | 8/8 | [spec](console-polish/spec.md) · [design](console-polish/design.md) · [handoff](console-polish/handoff.md) |
| 8 | **Judge feedback** (2026-11-04) | A human reviews a judged run; the same judges reconsider with the review as evidence, not an order. Reviews are distilled into guidance that users approve in the console and that is stored in the deployment's own archive, after evaluation on held-out runs. This adds panel–human agreement (gap 3) | Standard | Shipped (PR #5) | 15/15 | [spec](judge-feedback/spec.md) · [design](judge-feedback/design.md) · [launch](judge-feedback/launch.md) · [handoff](judge-feedback/handoff.md) |

## Slices open for the team (2026-11-04)

Four self-contained slices, one per person. Each spec says what exists, the testable acceptance criteria, what not to touch, and how to check the work, so you can hand it to Kiro or your tool of choice as is. Take one, put your name in its Owner line and in the table below, and follow "How to take a slice".

| Slice | Purpose | Size | Status | Owner | Spec |
| --- | --- | --- | --- | --- | --- |
| **Evals in plain language** | A plain summary on every run ("what was found, how much to trust it, what to check by hand"), built from the archive with no new model calls | about half a day | Open | — | [spec](plain-verdict/spec.md) |
| **Prompt compliance** | Check each result against **every** condition in the prompt (e.g. "within 10 miles of a protected area, inside ZIP 75082") and show evidence or its absence, per claim | about a day (splits in two) | Open | — | [spec](prompt-compliance/spec.md) |
| **Visual design** | Make the console read as a designed product on a projector: type, spacing, hierarchy, a matching report; visual only, behavior unchanged | about a day | Open | — | [spec](visual-design/spec.md) |
| **Presentation** | An interactive HTML deck (10 slides), a live demo of **judging** an already-built run, a one-pager for ADB, and Q&A prep; every number sourced to the repo | about a day | In progress (built; rehearsal pending) | Miguel | [spec](presentation/spec.md) · [handoff](presentation/handoff.md) |

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

## Changes without a spec

Fixes and small features, each with a test and recorded in its commit. All on 2026-11-04.

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

## Open work

| Item | Purpose | Status | Owner and default |
| --- | --- | --- | --- |
| **ADB's rubric and task** | Score against ADB's own criteria, not our generalized rubric | Blocked on Clay (V191) | Clay. Default: `rubrics/geo-dataset-v1.yaml`; ADB's drops in as YAML |
| **Answer key** for outcome correctness | Judge whether found sites are real, not just traceable, e.g. solar farms against USPVDB, with a measured recall and precision criterion | Open | Team. See [gaps](judging/gaps.md) |
| **Human-expert ratings** of about 20 runs | Validate the panel against experts, as the GRA paper did (expert α ≈ 0.56) | Open | Team |
| **A gate for unconfirmed results** | A run whose imagery checks confirm no candidate still scores about 96 and High | Open, proposed 2026-11-04 | Team |
| **AgentCore redeploy** | The agent-side fixes (area narrowing, LGND token refresh) reach AgentCore runs only after a redeploy | **Done** 2026-11-04 (run `a5670c6b` used them; [console-polish handoff](console-polish/handoff.md)) | Redeploy after any change to `agent/`, `tools/` or `prompts/agent/` |
| **Tile backfill** for older runs | Archive result tiles for runs made before the tile cache | Open (2 runs done) | Team: the loop in [tile-cache launch](tile-cache/launch.md) |
| **Unrun example cards** | 15 of the 16 cards have verified areas but no full run | Open | Team: reword or drop a card whose feature LGND can't find |
| Harness follow-ups | A long synchronous AgentCore call (spike S2), the OSM answer-key count (S6), the token cap for country-scale prompts | Open | See the [eval-harness](eval-harness/handoff.md) and [layering](layering/handoff.md) handoffs |
