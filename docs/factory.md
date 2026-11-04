# The Factory: Every Effort, Its Purpose and Status

The ledger of work on the Team Foundry eval harness: every spec-to-handoff effort, the changes made without a spec, and what is still open. Each effort follows the same path: **spec** (problem and testable acceptance criteria), then **design** (options, failure modes, rollback), then **build**, then **verify** (each criterion proven by something that ran, recorded in the **handoff**). Small efforts skip the design. Update this page when an effort starts, changes status or ships (see [CONTRIBUTING](../CONTRIBUTING.md#documentation-conventions)).

**Status key:** **Shipped**: built, verified and merged to the working branch. **In progress**: being built or verified. **Open**: decided but not started. **Blocked**: waiting on someone outside the team.

## Efforts with a spec

| # | Effort | Purpose | Track | Status | ACs proven | Records |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Eval harness** (2026-11-03) | Run an agent on AgentCore with RODA and LGND Geo, capture every model and tool decision as OpenTelemetry spans in an S3 archive, check the trace, grade claim provenance, report, replay, compare | Standard | Shipped | 11/11 | [spec](eval-harness/spec.md) · [design](eval-harness/design.md) · [spikes](eval-harness/spikes.md) · [handoff](eval-harness/handoff.md) |
| 2 | **Layering** (2026-11-04) | Separate `core` / `tools` / `agent` / `analysis` / `harness`, with prompts as files and tool knowledge in `tools/`, enforced by tests | Quick | Shipped | 4/4 | [spec](layering/spec.md) · [handoff](layering/handoff.md) |
| 3 | **Judging and console** (2026-11-04) | Score each run's workflow and output against a generalized rubric with a cross-family judge panel, with agreement, confidence and calibration. The Team Foundry console (FastAPI) to run, watch and score | Standard | Shipped (panel revised: [tribunal of three](judging/handoff.md)) | 15/15 | [spec](judging/spec.md) · [design](judging/design.md) · [guide](judging/guide.md) · [gaps](judging/gaps.md) · [paper notes](judging/paper-notes.md) · [handoff](judging/handoff.md) |
| 4 | **Example cards** (2026-11-04) | One-click example prompts for every continent, Asia first, mostly in ADB developing member countries, each with a verified official boundary | Quick | Shipped | 8/8 | [spec](example-cards/spec.md) · [handoff](example-cards/handoff.md) |
| 5 | **Tile cache** (2026-11-04) | Archive each run's result tiles so archived runs replay their imagery offline; serve basemaps and tiles from a disk cache | Standard | Shipped | 10/10 | [spec](tile-cache/spec.md) · [design](tile-cache/design.md) · [launch](tile-cache/launch.md) · [handoff](tile-cache/handoff.md) |
| 7 | **Console polish** (2026-11-04) | Dark theme across the console, report and API docs; a docked result panel instead of clipped popups; step links that scroll the timeline, not the page; the area-narrowing fix and the LGND token refresh behind run `fdacf7cf` | Standard | Shipped | 8/8 | [spec](console-polish/spec.md) · [design](console-polish/design.md) · [handoff](console-polish/handoff.md) |
| 6 | **Docs pass** (2026-11-04) | Documentation in ship shape: an accuracy audit against the code, the developer guide, CONTRIBUTING, the docs index, this ledger, and a test that keeps the links and references true | Quick | Shipped | 5/5 | [spec](docs-pass/spec.md) · [handoff](docs-pass/handoff.md) |

## Changes without a spec

Fixes and small features, each with a test and recorded in its commit. All on 2026-11-04.

| Change | Why | Commit |
| --- | --- | --- |
| Runs whose model calls all failed are **not scored**, not FAILED | An expired-credentials run was scored FAILED 0, and judging cost $0.06 | `5f3c15c` |
| Judge **tribunal of three**, with reserves that stand in for a failed judge | The user's call: three judges, dropping the most problematic. Grok was slowest and was the only one to error | `74d434d`, `08401ae` |
| The report renders the answer as **Markdown** | It showed raw `**` and `\|---\|` next to formatted sections | `e4ef776` |
| **Area lookup** only accepts boundaries and places; enforcement keeps a narrower area | "Northern California" resolved to a 20 m building, and a run hit the 40-step limit | `c041b6f` |
| Runs list from **saved rows**; documented API at `/api/docs` | The runs list took about 7 s (S3 re-reads); the API docs were bare | `07d197c` |
| Runs API **cursor paging** and filters; every API consumer updated | Paging asked for; consumers audited | `bd2ae60`, `bd2970a` |

## Open work

| Item | Purpose | Status | Owner and default |
| --- | --- | --- | --- |
| **ADB's rubric and task** | Score against ADB's own criteria, not our generalized rubric | Blocked on Clay (V191) | Clay. Default: `rubrics/geo-dataset-v1.yaml`; ADB's drops in as YAML |
| **Answer key** for outcome correctness | Judge whether found sites are real, not just traceable, e.g. solar farms against USPVDB, with a measured recall and precision criterion | Open | Team. See [gaps](judging/gaps.md) |
| **Human-expert ratings** of about 20 runs | Validate the panel against experts, as the GRA paper did (expert α ≈ 0.56) | Open | Team |
| **A gate for unconfirmed results** | A run whose imagery checks confirm no candidate still scores about 96 and High | Open, proposed 2026-11-04 | Team |
| **AgentCore redeploy** | The agent-side area-narrowing fix (`c041b6f`) reaches AgentCore runs only after a redeploy | Open | Team: `cd infra && CDK_DOCKER=podman npx aws-cdk deploy` |
| **Tile backfill** for older runs | Archive result tiles for runs made before the tile cache | Open (2 runs done) | Team: the loop in [tile-cache launch](tile-cache/launch.md) |
| **Unrun example cards** | 15 of the 16 cards have verified areas but no full run | Open | Team: reword or drop a card whose feature LGND can't find |
| Harness follow-ups | A long synchronous AgentCore call (spike S2), the OSM answer-key count (S6), the token cap for country-scale prompts | Open | See the [eval-harness](eval-harness/handoff.md) and [layering](layering/handoff.md) handoffs |
