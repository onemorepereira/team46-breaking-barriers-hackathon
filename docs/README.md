# Documentation

Start with the [project README](../README.md) for the mission, what we built and why. This page lists the documents by what you're trying to do. [The factory](factory.md) is the ledger of every effort and its status.

## Guides: start here

| Doc | For |
| --- | --- |
| [Developer guide](developer-guide.md) | Setting up, running, configuring (every `harness.yaml` key), the CLI, extending (prompts, rubrics, judges, tools), testing, troubleshooting |
| [Contributing](../CONTRIBUTING.md) | Branch and commit rules, the checks CI runs, the rules the tests enforce, the doc conventions |
| [How a run is scored](judging/guide.md) | The rubric, the judge tribunal, recusal and stand-ins, gates, confidence, agreement, calibration |
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
| Presentation | [README](presentation/README.md) · [deck](presentation/deck.html) · [demo script](presentation/demo.md) · [claims](presentation/claims.md) · [Q&A](presentation/qa.md) · [one-pager](presentation/one-pager.md) · [spec](presentation/spec.md) · [handoff](presentation/handoff.md) | The interactive HTML deck, the judging-only live demo, and their sources |

**Open slices** (specs for the team; status in [the factory](factory.md#slices-open-for-the-team-2026-11-04)): [plain-language evals](plain-verdict/spec.md) · [prompt compliance](prompt-compliance/spec.md) · [visual design](visual-design/spec.md)

## Data and configuration in the repo

| Path | What it is |
| --- | --- |
| [`harness.yaml`](../harness.yaml) | All settings, with each price sourced in a comment; reference in the [developer guide](developer-guide.md#5-configuration-reference-harnessyaml) |
| [`rubrics/geo-dataset-v1.yaml`](../rubrics/geo-dataset-v1.yaml) | The default scoring rubric |
| [`prompts/`](../prompts) | Every text sent to a model: `agent/`, `harness/`, `judge/`, `tasks/` |
| [`suites/`](../suites) | Prompt × model suites for `harness run --suite` |
| [`harness/web/static/examples.json`](../harness/web/static/examples.json) | The console's example cards |
| [`LICENSE`](../LICENSE) | Apache-2.0 |
