# Documentation

Start with the [project README](../README.md) for the mission, what we built and why. This page lists the documents by what you're trying to do. [The factory](factory.md) is the ledger of every effort and its status.

## Guides: start here

| Doc | For |
| --- | --- |
| [Connected evidence workspace](workspace/README.md) | Supplied React UI connected to the live backend: launch, build, evidence, human review and deployment |
| [Developer guide](developer-guide.md) | Setting up, running, configuring (every `harness.yaml` key), the CLI, extending (prompts, rubrics, judges, tools), testing, troubleshooting |
| [Contributing](../CONTRIBUTING.md) | Branch and commit rules, the checks CI runs, the rules the tests enforce, the doc conventions |
| [How a run is scored](judging/guide.md) | The rubric, the measured criteria, the judge tribunal, recusal and stand-ins, gates, confidence, agreement, calibration |
| Console API reference: `/api/docs` on a running console (`uv run harness ui`) | Every endpoint, request and response field, error, and live-event type. Source: `harness/web/api_docs.py` |

## Core documents: the event's briefs

The README cites these by line, as `T…` and `V…` footnotes.

| Doc | What it is |
| --- | --- |
| [Technical brief](Clay-Foundry-Technical-Hackathon.md) (T) | Clay's technical brief for the hackathon: tracks, stack, evaluation |
| [Vision brief](Clay-Foundry-Vision-Hackathon.md) (V) | Clay's vision brief: the mission, ADB, judging |
| [Suggested hackathon edits](<suggested hackathon edits.pdf>) | Clay's Nov 3 edits, folded into both briefs |

## Feature records

**[The factory](factory.md)** is the ledger of every effort: its purpose and status, the changes made without a spec, and the open work.

Each folder holds a feature's spec (problem and acceptance criteria), its design (options, failure modes, rollback) and its handoff (what shipped, and how each criterion was proven). The records are dated history: later changes add dated notes, and the guides above describe the present.

| Feature | Records | Summary |
| --- | --- | --- |
| Eval harness | [spec](eval-harness/spec.md) · [design](eval-harness/design.md) · [spikes](eval-harness/spikes.md) · [handoff](eval-harness/handoff.md) | The agent on AgentCore with RODA and LGND Geo, trace capture as OpenTelemetry spans, the S3 archive, claim provenance, reports, replay, compare |
| Layering | [spec](layering/spec.md) · [handoff](layering/handoff.md) | `core` / `tools` / `agent` / `analysis` / `harness`, with prompts as files, enforced by tests |
| Judging and console | [spec](judging/spec.md) · [design](judging/design.md) · [guide](judging/guide.md) · [gaps](judging/gaps.md) · [paper notes](judging/paper-notes.md) · [handoff](judging/handoff.md) | The generalized rubric, the judge tribunal, agreement and calibration, the Team Foundry console. The gap analysis against the briefs, and notes on the GRA paper |
| Example cards | [spec](example-cards/spec.md) · [handoff](example-cards/handoff.md) | One-click prompts for every continent, Asia first |
| Tile cache | [spec](tile-cache/spec.md) · [design](tile-cache/design.md) · [launch](tile-cache/launch.md) · [handoff](tile-cache/handoff.md) | Result tiles archived with each run; basemaps and tiles served from a disk cache |
| Console polish | [spec](console-polish/spec.md) · [design](console-polish/design.md) · [handoff](console-polish/handoff.md) | Dark theme, a docked result panel, timeline-only step jumps, and the area-narrowing fix behind run `fdacf7cf` |
| Docs pass | [spec](docs-pass/spec.md) · [handoff](docs-pass/handoff.md) | This index, the developer guide and CONTRIBUTING, plus the accuracy audit |
| ADB alignment | [LGND/Ode report, for us](adb-alignment/lgnd-ode-brief.md) · [spec](adb-alignment/spec.md) · [design](adb-alignment/design.md) · [handoff](adb-alignment/handoff.md) | Reference checks, licences per run, per-concept and transfer results |
| AWS hardening | [spec](aws-hardening/spec.md) · [handoff](aws-hardening/handoff.md) | The stack against AWS's documented practice: IAM, the archive bucket, logs, the container |
| Judge feedback | [spec](judge-feedback/spec.md) · [design](judge-feedback/design.md) · [launch](judge-feedback/launch.md) · [handoff](judge-feedback/handoff.md) | Humans review a judgement; judges reconsider; reviews become evaluated guidance |
| Evaluations in plain language, prompt compliance, value matching (PR #7) | [plain-language spec](plain-verdict/spec.md) · [handoff](plain-verdict/handoff.md) · [prompt-compliance spec](prompt-compliance/spec.md) · [handoff](prompt-compliance/handoff.md) · [value-matching spec](value-matching/spec.md) · [handoff](value-matching/handoff.md) | A plain summary on every run, a check of each result against every condition in the prompt (`condition_compliance`), and stricter matching of cited values |
| Workspace map popups | [handoff](workspace-map-popups/handoff.md) | Imagery popups and clickable tiles on the workspace map; archived runs open in about 2 s |
| Judging stability | [handoff](judging-stability/handoff.md) | Three passes judged at once, the score as the mean of every vote, re-judging that adds votes, and per-question review in the workspace |
| Observed scenes | [handoff](observed-scenes/handoff.md) | Result tiles show the scene LGND matched (Sentinel-2 or NAIP, that day), not a basemap mosaic |
| Visual check | [spec](visual-check/spec.md) · [design](visual-check/design.md) · [launch](visual-check/launch.md) · [handoff](visual-check/handoff.md) | Each reported site looked at in the sharpest open image (Vantor, OpenAerialMap, NAIP, Sentinel-2) by a vision model, scored as `visual_confirmation` (rubric v3) |
| Evaluation issues | [spec](evaluation-issues/spec.md) · [handoff](evaluation-issues/handoff.md) | Issue counts on the workspace's Evaluation sections, and a filter to show only those with issues |
| Map fit | [spec](map-fit/spec.md) · [handoff](map-fit/handoff.md) | Runs open and finish framed on the searched area's main part and the evidence, not on far-flung islands |
| Presentation | [README](presentation/README.md) · [deck](presentation/deck.html) · [demo script](presentation/demo.md) · [claims](presentation/claims.md) · [Q&A](presentation/qa.md) · [one-pager](presentation/one-pager.md) · [spec](presentation/spec.md) · [handoff](presentation/handoff.md) | The interactive HTML deck, the judging-only live demo, and their sources |

**Roadmap** (in [the factory](factory.md#roadmap)): fifteen efforts (R1–R15) that take the evaluator toward the LGND/Ode benchmark's requirements for ADB, ordered Now, Next and Later (R4, ranking metrics, has shipped); and eight (H1–H8) for site-risk screening, answering and evaluating "is this place too risky to build in?" from open hazard data, with a [hazard source catalog](site-risk-sources/catalog.md). The team slices of 2026-11-04 have all shipped except [visual design](visual-design/spec.md), which was not taken.

## Data and configuration in the repo

| Path | What it is |
| --- | --- |
| [`harness.yaml`](../harness.yaml) | All settings, with each price sourced in a comment; reference in the [developer guide](developer-guide.md#5-configuration-reference-harnessyaml) |
| [`rubrics/geo-dataset-v1.yaml`](../rubrics/geo-dataset-v1.yaml) | The default scoring rubric (version 3: 8 judged, 4 measured criteria) |
| [`prompts/`](../prompts) | Every text sent to a model: `agent/`, `harness/`, `judge/`, `tasks/` |
| [`suites/`](../suites) | Prompt × model suites for `harness run --suite`: `dallas-dc-v1` and the ADB T1 suite `adb-t1-v1` |
| [`references/`](../references/README.md) | Reference sets a run can be scored against (`harness reference`), e.g. USPVDB solar in Pecos County, TX |
| [`frontend/`](../frontend) | The workspace's React source; its build is committed in `harness/web/static/workspace/` |
| [`harness/web/static/examples.json`](../harness/web/static/examples.json) | The console's example cards |
| [`LICENSE`](../LICENSE) | Apache-2.0 |
