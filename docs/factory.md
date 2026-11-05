# The Factory: Roadmap and Record of Every Effort

The living catalog of work on the Team Foundry evaluator:
- what's next (the [roadmap](#roadmap));
- what has shipped and where its records are ([shipped](#shipped));
- what was decided against ([not taken](#not-taken));
- small changes made without a spec ([changes without a spec](#changes-without-a-spec));
- what is still unspecified ([backlog](#backlog)).

Every effort follows the same path:
1. **spec:** the problem and testable acceptance criteria;
2. **design:** options, failure modes and rollback; small (Quick) efforts skip it;
3. **build;**
4. **verify:** each criterion proven by something that ran, recorded in the **handoff**.

Update this page when an effort is specified, starts, changes status or ships (see [CONTRIBUTING](../CONTRIBUTING.md#documentation-conventions)), and take one by following [How to take an effort](#how-to-take-an-effort).

**Status key:**
- **Specified:** a spec is written and agreed in principle, and anyone can take it.
- **In progress:** being designed, built or verified, with an owner.
- **Shipped:** built, verified and merged.
- **Blocked:** waiting on someone outside the team.
- **Not taken:** specified, but deliberately not built.

## Roadmap

### Evaluator roadmap for ADB (specified 2026-11-05)

**Where it comes from:** the LGND/Ode inception report for ADB ([our paraphrase](adb-alignment/lgnd-ode-brief.md); the report isn't in the repo) **[ext]**, and the first run of our ADB T1 suite on 2026-11-05 (`adb-t1-v1-20261105T1103`) **[team]**.

**What the suite showed:**
- **Measured:** recall can only be measured where we have an answer key, and we have one (Pecos, 7 of 12 farms).
- **Blocked:** outside the US, agents can't start a search. LGND's Sentinel-2 index has no text search, so Gifu warehouses and Kathmandu substations returned nothing (scores 51.9 and 38.3).

**How the phases are ordered:**
- **Now:** makes the evaluator measure what ADB needs, comparable with LGND's own numbers, inside the report's harness window (October 20 to December 1).
- **Next:** answers the question the report leaves open, whether an off-the-shelf agent reproduces the workflow's performance (§5.8), plus ADB's cost, uncertainty and licence requirements.
- **Later:** covers the report's other analyst tasks and ADB's operational needs.

**Now**: measure what ADB needs

| # | Effort | Purpose | Report basis | Size | Depends on | Status | Owner | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | **ADB answer keys** | Reference sets for ADB's test places, so recall is measurable beyond Pecos: PLATEAU warehouses for Nagoya and Gifu built and tied to the T1 suite; DPWH (Manila) and PCRAFI (Port Vila) recorded as blocked candidates | §7.2.1, Table 1, Table 14, §7.4 | M (3–4 d) | — | Specified. DPWH and PCRAFI blocked on ADB legal (default: stay blocked); PLATEAU unblocked | — | [spec](adb-answer-keys/spec.md) |
| R2 | **Hand-labelled test blocks** | A labelling mode in the workspace that turns 1 km blocks traced on licence-clean imagery into a "complete within blocks" reference set | §3.2, §7.4, Table 7 | L (6–8 d) | — | Specified | — | [spec](test-block-labelling/spec.md) |
| R3 | **Seeded tasks** | Tasks carry seed example locations; runs record them and whether the agent used them; a seed-budget curve (score against number of seeds) | §1, Table 7, Table 9, Appendix B | M (3 d) | Complete reference for the curve (Pecos today) | Specified | — | [spec](seeded-tasks/spec.md) |
| R4 | **Ranking metrics** | recall@k, AUROC, AP and review effort (cells inspected to find 50/80/90% of assets) from the agent's ranked candidates | §5.7 Table 11, Table 7 | S–M (2 d) | — | In progress | Miguel | [spec](ranking-metrics/spec.md) · [design](ranking-metrics/design.md) · [handoff](ranking-metrics/handoff.md) |

**Next**: the open agentic question and ADB's operating requirements

| # | Effort | Purpose | Report basis | Size | Depends on | Status | Owner | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R5 | **Agent versus workflow** | Run LGND's classifier workflow on the same seeds and reference as an agent run and report the agent's gap in recall, review effort, cost and steps | §5.8 | M–L (4–5 d) | R3, R4 | Specified | — | [spec](agent-vs-workflow/spec.md) |
| R6 | **Uncertainty calibration** | Answers state a count with an 80% range and a confidence per site; coverage, Brier score and calibration error are checked against references | §4.2 (3), §5.5 | M (5 d) | R1 for the calibration half | Specified | — | [spec](uncertainty-calibration/spec.md) |
| R7 | **Transfer intervals** | Repeated runs, transfer levels per place pair (within city, cross-city, cross-country) and bootstrap 95% intervals on transfer gaps | §5.6 Table 10, §3.2 | S–M (3 d) | R1 for recall intervals | Specified. The 20-run suite needs a local `max_runs_per_suite` override (owner: Miguel) | — | [spec](transfer-intervals/spec.md) |
| R8 | **Cost per dataset** | Per-run LGND, compute, imagery, storage, review time and labels beside token costs; cost per found asset and per visually confirmed site | §4.2 (4–5), §5.7 | M (5 d) | R1 for cost per found asset | Specified. LGND's price per call unknown (default: unpriced, totals shown as "≥") | — | [spec](cost-per-dataset/spec.md) |
| R9 | **ADB deployment profile** | `profile: adb` drops non-commercial sources (Vantor, uncleared OAM items, the EOX basemap), extends licence refusals, and makes "presentable" a gate | Table 1, §4.2 (6), §7.4, §7.5 | S–M (3–4 d) | — | Specified. LGND Geo's terms needed (default: LGND runs blocked under `adb`) | — | [spec](adb-deployment-profile/spec.md) |

**Later**: the report's other tasks and ADB's operations

| # | Effort | Purpose | Report basis | Size | Depends on | Status | Owner | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R10 | **T2 sizing** | Score outlines and sizes: one-to-one footprint matching at IoU ≥ 0.5, area error, size-class accuracy and total-area ratio | Table 6 (T2), Table 7, Table 9, §5.5 | M–L (7–8 d) | R1; shares the claims-block extension with R6 | Specified. Adding `shapely` needs approval (alternative: rasterise at 1 m) | — | [spec](t2-sizing/spec.md) |
| R11 | **T3 register audit** | Score an agent's audit of a dated register (missing, misplaced, stale records) against held-out truth; first register from Pecos USPVDB | Table 5, Table 6 (T3), Table 7 | 3–4 d | R1, R3 | Specified | — | [spec](t3-register-audit/spec.md) |
| R12 | **T4 damage count** | Score per-tier damage counts (unaffected, damaged, destroyed) and each asset's tier against a labelled event set; evaluates a count, produces no damage layer | Table 5, Table 6 (T4), Table 9, §2.2 | 4 d + 1 d labelling | R1 | Specified. Blocked on an event with licence-clean labelling imagery | — | [spec](t4-damage-count/spec.md) |
| R13 | **District scoring** | Reference metrics broken down per district or hazard zone, from a licensed zone set; `zones.csv` in compare | Table 7 | 2–3 d | — | Specified | — | [spec](district-scoring/spec.md) |
| R14 | **Reproducibility bundle** | `harness bundle` exports a run or suite with its method files, licences and repeat commands, and `bundle verify` reproduces its scores offline | §4.2 (7) | 3 d | R9 decides what an ADB bundle redacts | Specified | — | [spec](reproducibility-bundle/spec.md) |
| R15 | **ADB rubric and expert calibration** | ADB's rubric dropped in as YAML; the panel calibrated against ADB experts on 20 runs, rated blind; reviews seed guidance | §5.8, (V191) | 3 d + about 10 expert-hours | R9 | Specified. Blocked on Clay for ADB's rubric (V191) and on ADB for expert time; a stand-in run with team reviewers doesn't wait | — | [spec](adb-rubric-calibration/spec.md) |

All fifteen are Standard track (each needs a design before build). Report references are its section and table numbers **[ext]**.


### Other planned work

| Item | Purpose | Status | Owner and default |
| --- | --- | --- | --- |
| **A gate for unconfirmed results** | A run whose checks confirm no candidate can still score high and High confidence | Partly addressed: the [visual check](visual-check/handoff.md) lowers the score when sites aren't seen (Abilene wind 96.2 → 89.4). There's no gate on the score or the confidence | Team. Default: no gate until answer keys (R1) exist |
| **Visual-check follow-ups** | Sites given as separate latitude and longitude claims get no check; one vote per site (a second checker from another family); image dates not compared with the asset; images coarser than Sentinel-2 can win the source order (a 31 m OpenAerialMap image was used for Manila bridges) | Open | Team. See the [visual-check handoff](visual-check/handoff.md#known-limits-and-follow-ups) |
| **Tile backfill** for older runs | Archive result tiles for runs made before the tile cache | Open | Team: the loop in [tile-cache launch](tile-cache/launch.md) |
| **Unrun example cards** | 15 of the 16 cards have verified areas but no full run | Open | Team: reword or drop a card whose feature LGND can't find |
| **Harness follow-ups** | A long synchronous AgentCore call (spike S2), the OSM answer-key count (S6), the token cap for country-scale prompts (two Kimi runs hit the 400,000-token limit on 2026-11-05), and an agent that called a tool that doesn't exist (`search_dataset_placeholder`, Kathmandu) | Open | See the [eval-harness](eval-harness/handoff.md) and [layering](layering/handoff.md) handoffs |

## Shipped

All merged to `main`. Dates are GitHub merge dates (UTC). "ACs" is acceptance criteria proven out of those specified.

| Effort | Purpose | Track | ACs | Shipped | Owner | Records |
| --- | --- | --- | --- | --- | --- | --- |
| **Eval harness** | Run an agent on AgentCore with RODA and LGND Geo, capture every model and tool decision as OpenTelemetry spans in an S3 archive, check the trace, grade claim provenance, report, replay, compare | Standard | 11/11 | PR #1, 2026-11-04 | Miguel | [spec](eval-harness/spec.md) · [design](eval-harness/design.md) · [spikes](eval-harness/spikes.md) · [handoff](eval-harness/handoff.md) |
| **Layering** | Separate `core` / `tools` / `agent` / `analysis` / `harness`, with prompts as files and tool knowledge in `tools/`, enforced by tests | Quick | 4/4 | PR #1, 2026-11-04 | Miguel | [spec](layering/spec.md) · [handoff](layering/handoff.md) |
| **Judging and console** | Score each run's workflow and output against a generalized rubric with a cross-family judge panel, with agreement, confidence and calibration; the Team Foundry console (FastAPI). Since revised: a tribunal of three (Opus, DeepSeek, Kimi, with reserves) | Standard | 15/15 | PR #1, 2026-11-04 | Miguel | [spec](judging/spec.md) · [design](judging/design.md) · [guide](judging/guide.md) · [gaps](judging/gaps.md) · [paper notes](judging/paper-notes.md) · [handoff](judging/handoff.md) |
| **Example cards** | One-click example prompts for every continent, Asia first, mostly in ADB developing member countries, each with a verified official boundary | Quick | 8/8 | PR #1, 2026-11-04 | Miguel | [spec](example-cards/spec.md) · [handoff](example-cards/handoff.md) |
| **Tile cache** | Archive each run's result tiles so archived runs replay their imagery offline; serve basemaps and tiles from a disk cache | Standard | 10/10 | PR #1, 2026-11-04 | Miguel | [spec](tile-cache/spec.md) · [design](tile-cache/design.md) · [launch](tile-cache/launch.md) · [handoff](tile-cache/handoff.md) |
| **Docs pass** | Documentation in ship shape: an accuracy audit, the developer guide, CONTRIBUTING, the docs index, this catalog, and a test that keeps links and references true | Quick | 5/5 | PR #1, 2026-11-04 (follow-up PR #4) | Miguel | [spec](docs-pass/spec.md) · [handoff](docs-pass/handoff.md) |
| **Console polish** | Dark theme across the console, report and API docs; a docked result panel; step links that scroll the timeline; the area-narrowing fix and the LGND token refresh | Standard | 8/8 | PR #1, 2026-11-04 | Miguel | [spec](console-polish/spec.md) · [design](console-polish/design.md) · [handoff](console-polish/handoff.md) |
| **Presentation** | An interactive HTML deck, a live demo of judging an already-built run, a one-pager for ADB, and Q&A prep; every number sourced to the repo. Rehearsal (AC6) not logged | Standard | 5/6 | PR #3, 2026-11-04 (slides in #6, #10, #11; 5-minute deck #16; brought up to date #38) | Miguel | [spec](presentation/spec.md) · [handoff](presentation/handoff.md) |
| **Judge feedback** | A human reviews a judged run and the judges reconsider with the review as evidence, not an order; reviews distilled into guidance that users approve, evaluated on held-out runs | Standard | 15/15 | PR #5, 2026-11-04 | Miguel | [spec](judge-feedback/spec.md) · [design](judge-feedback/design.md) · [launch](judge-feedback/launch.md) · [handoff](judge-feedback/handoff.md) |
| **Evals in plain language** | A plain summary on every run ("what was found, how much to trust it, what to check by hand"), built from the archive. The three-real-archive readability check (AC6) is not recorded | Quick | 5/6 | PR #7, 2026-11-04 | Aditya | [spec](plain-verdict/spec.md) · [handoff](plain-verdict/handoff.md) |
| **Prompt compliance** | Check each result against every condition in the prompt, with evidence or its absence per claim (rubric v2). Live ZIP run `d0bfb674` checked; planted-defect calibration under v2 not recorded | Standard | — | PR #7, 2026-11-04 | Aditya | [spec](prompt-compliance/spec.md) · [handoff](prompt-compliance/handoff.md) |
| **Value matching** | Reject opposite verdicts, coordinates spliced across records and failed tool output; label older replays (matcher version 3) | Quick | — | PR #7, 2026-11-04 | Aditya | [spec](value-matching/spec.md) · [handoff](value-matching/handoff.md) |
| **AWS hardening** | A conditioned trust policy, scoped logs and metrics, open-data reads limited to other accounts, a versioned and access-logged archive, 30-day runtime logs, a non-root pinned scanned container | Quick | 7/7 | PR #8, 2026-11-04 (deployed) | Miguel | [spec](aws-hardening/spec.md) · [handoff](aws-hardening/handoff.md) |
| **ADB alignment** | Reference sets scored under the LGND/Ode matching rule (recall, precision, count ratio, lift); data and licences per run; per-concept and transfer reporting; a T1 suite over the report's concepts and places | Standard | 10/10 | PR #9, 2026-11-04 | Miguel | [what the report means for us](adb-alignment/lgnd-ode-brief.md) · [spec](adb-alignment/spec.md) · [design](adb-alignment/design.md) · [handoff](adb-alignment/handoff.md) |
| **Foundry workspace UI** | The Foundry React UI at `/workspace/`, connected to the live evaluation backend, then reworked for usability, summaries and quick score feedback | — | — | PRs #12–#13, 2026-11-04; #15, 2026-11-05 | Aditya (review fixes: Miguel) | [README](workspace/README.md) · [review fixes](workspace/review-fixes.md) |
| **Workspace map popups** | Imagery on the workspace map with its details; archived runs open in about 2 s instead of 6–15 s. The popups were later replaced by an inspector beside the map (PR #15) | — | — | PR #14, 2026-11-05 | Miguel | [handoff](workspace-map-popups/handoff.md) |
| **Judging stability and workspace review** | Scores that settle rather than flip (mean of every vote over three concurrent passes), judging in about 20 s, per-question human review in the workspace | — | — | PR #17, 2026-11-05 | Miguel | [handoff](judging-stability/handoff.md) |
| **Observed scenes** | Result tiles show the scene LGND matched (sensor, date, place), not a basemap mosaic | — | — | PR #30, 2026-11-05 | Miguel | [handoff](observed-scenes/handoff.md) |
| **Visual check** | Each reported site is looked at in the sharpest open image (Vantor, OpenAerialMap, NAIP, Sentinel-2) by a vision model, and scored as `visual_confirmation` (rubric v3) | Standard | 11/11 | PR #33, 2026-11-05 | Miguel | [spec](visual-check/spec.md) · [design](visual-check/design.md) · [launch](visual-check/launch.md) · [handoff](visual-check/handoff.md) |
| **Evaluation issue filter** | Red issue counts on Evaluation sections and a filter to show only sections with issues | Quick | 5/5 | PR #34, 2026-11-05 | Miguel | [spec](evaluation-issues/spec.md) · [handoff](evaluation-issues/handoff.md) |
| **Map fit** | Runs open and finish framed on the searched area's main part and the evidence, not on far-flung islands | Quick | 3/3 | PR #35, 2026-11-05 | Miguel | [spec](map-fit/spec.md) · [handoff](map-fit/handoff.md) |

## Not taken

| Effort | Purpose | Why not | Spec |
| --- | --- | --- | --- |
| **Visual design** | Make the console read as a designed product on a projector: type, spacing, hierarchy, a matching report | The Foundry [workspace UI](workspace/README.md) (PRs #12–#13, refined through #36) became the presented interface instead | [spec](visual-design/spec.md) |

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
| **Team slices**: four self-contained specs, plus how to take one and the merge order | The team worked in parallel on the day before the presentation | `b3d5520` |
| **`harness.local.yaml`**: a git-ignored override merged over `harness.yaml` | Teammates work in their own AWS sandboxes without editing the shared config | `ec7ea92` |
| **Branch rule**: every change goes on a branch from `main`, through a PR | `main` is the shared baseline | PRs #1–#3 |
| **AgentCore redeploy** after the agent-side fixes (area narrowing, LGND token refresh) | Agent changes reach AgentCore runs only after a redeploy (run `a5670c6b` used them) | [console-polish handoff](console-polish/handoff.md) |
| **Workspace live panel** animates while the agent and judges work, and fits without scrolling (2026-11-05) | The live trail needed scrolling and looked idle while judges worked | PRs #20, #25 |
| **Workspace layout fixes**: Team Foundry mark and favicon; the build hotfix; the docked tile panel and phone layout; no header Evaluation button; imagery on first view in a full-height slide-out tile panel; a picked thumbnail opens at its title (2026-11-05) | Review of the merged workspace | PRs #19, #22, #23, #24, #26, #28 |
| **Map credit and legend**: the imagery credit stays folded unless hovered or focused, is compact at every width, and the legend stops short of it (2026-11-05) | The legend and the attribution overlapped | PRs #21, #29, #31 |
| **Agent image installs `libexpat1`** (2026-11-05) | `rasterio`, added for observed scenes, didn't load in the agent image without it | PR #32 |
| **Every inspector image shows its source pill**, and a cached image no longer sticks on "Fetching" (2026-11-05) | Only some images named their source | PR #36 |
| **Docs accuracy pass**: every living doc checked against `main`; records carry status and dated later-change notes (2026-11-05) | Docs had drifted through 36 PRs | PR #37 |
| **Decks brought up to date**, a fresh Pecos demo run (`79c18997`), and the event AWS account ID moved out of the repo into the private `harness.local.yaml` (2026-11-05) | The decks described median scoring and deleted runs; the account ID didn't belong in Git | PR #38 |

## Backlog

Ideas with no spec yet. Promote one by writing its spec and adding it to the [roadmap](#roadmap).

- **A second vision vote per site** (see Visual-check follow-ups above); worth specifying once R1 answer keys can measure whether it helps.
- **A web-source tool for the agent**: the report's agentic dimensions include combining imagery with web sources (§5.8) **[ext]**, and our agent has none.
- **Measured period coverage**: whether searches covered the requested time period is judged today, not measured (§5.8) **[ext]**.

## How to take an effort

1. **Set up:** follow the [developer guide](developer-guide.md) (`uv sync`; `uv run pytest` passes offline). For anything live, set up [your own AWS sandbox](#your-own-aws-sandbox), and keep its temporary credentials in your shell (they expire every few hours).
2. **Claim it:** put your name in the spec's Owner line and in its row here, and set it **In progress**.
3. **Branch:** `git switch -c feat/<slug> main` (or `fix/`, `docs/`, `chore/`). Never commit to `main` directly, and never commit credentials.
4. **Get runs to look at:** a fresh clone has no runs, because runtime data is never committed. Make a few with `uv run harness ui` and the example cards, or `uv run harness run --prompt prompts/tasks/dallas-dc.md --model sonnet --backend local`. Each costs about $0.20–1.00 in Bedrock and takes 1–7 minutes. Don't restart the console while one of your runs is going, or the run dies.
5. **Build to the spec:** keep to its non-goals, and if the spec is wrong or unclear, fix the spec first and say so in the PR. Standard and Full efforts write a `design.md` first. Run the checks the spec lists, plus `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`, and for UI work the browser probes in `tests/browser/`.
6. **Finish:**
   - write `docs/<slug>/handoff.md`: what shipped, and each acceptance criterion with what proved it (a test name, a command, a screenshot, a run ID);
   - set the spec's Status to `Built`;
   - move its row from the roadmap to [Shipped](#shipped);
   - open a PR to `main`, and ask a teammate who didn't build it to review it.

Changes to `agent/`, `tools/`, `prompts/agent/`, dependencies or the `Dockerfile` reach AgentCore runs only after a redeploy: `cd infra && CDK_DOCKER=podman npx aws-cdk deploy`.

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
