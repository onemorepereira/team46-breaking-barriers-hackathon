# Team Foundry (Team 46) — Clay Earth Dataset Foundry

Nov 3, 2026 · @Miguel · updated Nov 4 with what we built

> **Sources.** Each statement cites where it comes from. Most cite the two briefs, [Technical](docs/Clay-Foundry-Technical-Hackathon.md) (T) and [Vision](docs/Clay-Foundry-Vision-Hackathon.md) (V), with line numbers. Both briefs include Clay's suggested edits from [the Nov 3 PDF](<docs/suggested hackathon edits.pdf>). Statements that are not in either brief carry a tag instead: **[team]** for our own decisions, **[event]** for event logistics from the organizers, and **[ext]** for general background.

## Mission

Build an open-source sandbox that **observes, summarizes and scores** an AI agent doing a geospatial dataset task[^T8][^V7], so Clay and ADB can tell whether to trust what the agent built[^V13].

## Scope: Track 1, the ADB agentic eval

The briefs now offer two tasks, the ADB agentic eval and caption generation[^T27]; the open third track was removed in the Nov 3 edits **[event]**. We focus on **Track 1, the ADB agentic eval**, which both briefs name as the starting point[^T9][^V70] **[team]**. Caption generation (Track 2) is out unless Track 1 works end to end first[^T34][^V180] **[team]**.

Track 1 evaluates an agent doing an ADB-style "how to use AI / build datasets" task. Its inputs are an input dataset, the harness(es) under test and synthetic prompts that teams bring; it is scored against a rubric, and its output is the traces gathered from observing the system[^T31][^V70]. The task, the dataset and the rubric come from Clay[^V191].

## What we built

A working Track 1 evaluation harness, on branch `design/eval-harness` **[team]**. An agent finds sites from a prompt, for example data centers in Richardson, TX, or farmland in Khammouane, Laos. Every model and tool decision is recorded. Each run is then checked, graded, **scored by a five-judge panel**, summarized and reported from the archive alone, and shown in the **Team Foundry console** **[team]**.

- Harness: [spec](docs/eval-harness/spec.md), [design](docs/eval-harness/design.md), [spike results](docs/eval-harness/spikes.md), [handoff and verification](docs/eval-harness/handoff.md).
- Scoring and console: [**how a run is scored**](docs/judging/guide.md), [spec](docs/judging/spec.md), [design](docs/judging/design.md), [paper notes (GRA)](docs/judging/paper-notes.md), [gaps against the briefs](docs/judging/gaps.md), [handoff](docs/judging/handoff.md).

### How it works

```
harness CLI ──▶ AgentCore Runtime ──▶ Strands agent ──▶ Bedrock model (Claude Sonnet 5.5 or Kimi K3)
   │                                       ├─▶ RODA MCP server (public dataset catalog)
   │                                       └─▶ LGND Geo MCP server (NAIP imagery search and checks)
   │                                  every span ──▶ S3 archive (JSONL)  +  CloudWatch (AgentCore Observability)
   ├─ reads the archive ──▶ check · claim provenance · area compliance · signals · summary · report · replay · compare
   ├─ judge panel ──▶ evidence dossier ──▶ 5 judges, 5 model families (Bedrock) ──▶ median · agreement · confidence
   └─ Team Foundry console (FastAPI) ──▶ live steps in plain English · satellite map and tiles · KPIs · scorecard
```

**[team]**

- **The agent** runs on Bedrock AgentCore Runtime[^T105] and uses the RODA and LGND Geo MCP servers[^T34][^T144] **[team]**. Its task is to find data centers within 50 km of downtown Dallas, TX **[team]**.
- **Every decision is a span.** Hooks in the agent record each model call (full input, output, reasoning, tokens) and each tool call (arguments, full result, latency, retries) as OpenTelemetry `harness.*` spans **[team]**. A processor archives every span to S3 at the moment it ends **[team]**.
- **Claims are traceable.** Each tool result is stamped with a label like `[ref T3]`. The agent must cite that label for every claim, with one value copied verbatim from one tool result **[team]**. The harness grades each claim as **matched**, **mismatch** or **unsourced** against the full archived result **[team]**.
- **Reports work offline.** The report, replay and comparison read only the archive, so a recorded run can be re-graded without calling the model again[^T121][^V114] **[team]**.
- **OpenTelemetry is the only telemetry API.** The deployed backend is AgentCore Observability (CloudWatch); a CI test proves the exporter can be swapped by config alone[^T177][^V164] **[team]**.
- **A panel scores every run.** A generalized rubric ([`rubrics/geo-dataset-v1.yaml`](rubrics/geo-dataset-v1.yaml)) scores the workflow and the output, matching the brief's two dimensions[^T116][^V110]:
  - two criteria are measured by code: claim provenance and area compliance;
  - eight are judged by Claude Opus 5.5, Grok 4.7, Kimi K3, DeepSeek V3.2 and Mistral Large 3, and each criterion's score is the median vote.

  A judge from the agent's own model family recuses itself. Every judgement carries its confidence (judge agreement plus trace integrity). `harness calibrate` proves the panel lowers the right criterion when we plant a defect **[team]**. See [how a run is scored](docs/judging/guide.md).
- **The console shows the run.** `harness ui` is a FastAPI app[^T99] built on the Tabler dashboard kit and MapLibre. It shows:
  - every step in plain English, with the raw span one click away;
  - the requested boundary and every result on Sentinel-2, USGS or NAIP imagery, with tiles;
  - score, cost, tool calls, tokens, claims verified and judge agreement up front.

  It carries the Team Foundry name and logo **[team]**.
- **Infrastructure is code.** A CDK stack creates the S3 archive, the arm64 agent image, a least-privilege role, the AgentCore runtime, the LGND login secret and an optional budget alert **[team]**. CI runs ruff, mypy, pytest (115 tests) and a gitleaks secret scan **[team]**.

### Code layout

Each layer may import only the ones listed, and `tests/test_layers.py` enforces it **[team]**:

| Layer | Holds | May import |
| --- | --- | --- |
| `core/` | archive store, span schema, geometry, prompt loader | nothing first-party |
| `prompts/` | every text sent to a model, as Markdown (`agent/`, `harness/`, `judge/`, `tasks/`) | n/a (data) |
| `rubrics/` | scoring rubrics as YAML; `geo-dataset-v1.yaml` is the default | n/a (data) |
| `tools/` | one package per MCP server (`roda/`, `lgnd/`): descriptors, result parsers, plain-English describers, client, auth; `registry.py`; test fakes | `core` |
| `agent/` | the Strands agent, hooks, telemetry, archive processor, entry points | `core`, `tools` |
| `analysis/` | pure grading of archived runs: checks, provenance, signals, timeline, report; `judging/` (rubric, measured criteria, dossier, panel aggregation, Krippendorff's α) | `core`, `tools` descriptors, result parsers and describers |
| `harness/` | CLI, config, invoking runs, area resolution, narrative, imagery; `judge.py` (the panel), `calibrate.py`; `web/` (the FastAPI console) | `core`, `analysis`, `tools` (never `agent`) |

### Quickstart

Needs `uv`, AWS credentials for the sandbox account, and podman or Docker for deploys **[team]**.

```sh
uv sync                                                       # Python 3.12 environment
uv run pytest                                                 # 115 tests, no AWS needed
uv run harness run --prompt prompts/tasks/dallas-dc.md --model sonnet --backend local      # agent on your machine
uv run harness run --prompt prompts/tasks/dallas-dc.md --model sonnet --backend agentcore  # agent on AgentCore
uv run harness run --suite suites/dallas-dc-v1.yaml           # both prompts on Sonnet 5.5 and Kimi K3
uv run harness compare <suite-id>                             # side-by-side table (HTML + CSV)
uv run harness replay <run-id>                                # rebuild a report from the archive only
uv run harness check <run-id>                                 # are all decisions recorded?
uv run harness ui                                             # Team Foundry console at http://127.0.0.1:8787
uv run harness judge <run-id> [--passes 3]                    # score a run with the 5-judge panel
uv run harness calibrate <run-id>                             # plant known defects; check the panel sees them
uv run harness agreement --all                                # Krippendorff's alpha across judged runs
uv run harness lgnd-login                                     # one-time browser login to LGND Geo
cd infra && CDK_DOCKER=podman npx aws-cdk deploy              # deploy or update the stack
```

**[team]** Reports land in `out/<run-id>/report.html`; settings live in `harness.yaml` **[team]**.

### Verified results

From the Verify stage on Nov 4; the evidence is in the [handoff](docs/eval-harness/handoff.md) **[team]**:

- **All 11 acceptance criteria were proven by commands that actually ran**, including live AgentCore runs, a CloudWatch query, an S3 archive listing and the CI tests **[team]**.
- **Every deployed run's trace check reports 0 missing fields, and 100% of decision spans were archived** **[team]**.
- **Claim rules matter.** With one verbatim value per claim, the Dallas suite graded 21 of 21 claims matched; before that rule, a run combining values from different tool results graded 0 of 6 **[team]**.
- **The models behave differently.** On the same task, Kimi K3 made far more traceable claims than Sonnet 5.5, but took 4–5 times longer and cost about 2–6 times more **[team]**. Suite `dallas-dc-v1-20261104T0450` on AgentCore, with all fixes applied **[team]**:

  | Prompt | Model | Steps | Input tokens | Est. cost | Time | Claims matched / mismatch / unsourced |
  | --- | --- | --- | --- | --- | --- | --- |
  | `dallas-dc` | Sonnet 5.5 | 7 | 80k | $0.18 | 43 s | 8 / 0 / 0 |
  | `dallas-dc` | Kimi K3 | 28 | 263k | $1.07 | 234 s | 35 / 0 / 0 |
  | `dallas-dc-strict` | Sonnet 5.5 | 7 | 79k | $0.17 | 25 s | 4 / 0 / 0 |
  | `dallas-dc-strict` | Kimi K3 | 11 | 93k | $0.38 | 94 s | 8 / 0 / 0 |

  Costs use Sonnet at $2 / $10 and Kimi at $3.30 / $16.50 per million input / output tokens, and count cached tokens at the full input rate **[team]**. All 4 runs report 0 missing fields **[team]**.
- **The agent found candidate sites.** Through LGND Geo's NAIP imagery search and imagery check, it reported candidate data-center sites near Dallas. Each one traces to a tool result, and their names and operators are still unconfirmed **[team]**.
- **Live runs found grader bugs, and replay re-graded old runs after the fixes**: JSON-escaped line breaks, Unicode escapes, cached prompt tokens counted as input, and tool errors counted twice **[team]**.

## Goals

1. **One loop, end to end.** An agent calls geospatial tools over MCP, and every run ends in a report[^T34][^V162].
2. **Trace everything, including the model's decisions.** Trace capture is our top priority **[team]**. Every run keeps its traces and inputs[^V34], and never gets judged on its final output alone[^T176]. See [Traceability](#traceability).
3. **Summarize the run.** A readable account, generated from the trace, of what the agent did and where it struggled[^T115].
4. **Score two things.** The workflow, from the traces[^T117], and the output, against a rubric[^T31][^T118]. ADB's rubric hasn't arrived[^V191], so a generalized rubric stands in and ADB's drops in as a file **[team]**. Two criteria are measured by code; eight are judged by a five-model, cross-family panel. Its median vote, agreement and confidence come with every score **[team]**.
5. **Keep observation pluggable.** The model and the tracing tool both stay swappable[^T10][^V113]. OpenTelemetry is the linchpin that proves it: a CI test sends the same agent spans to two different exporters, changing only config **[team]**. See [OpenTelemetry](#opentelemetry-the-pluggability-contract).
6. **Never fail the demo.** Recorded traces replay through the scorer and still produce a full report[^T121][^V114].
7. **Ship it open.** Apache-2.0[^V33], in an open-source repo Clay can access after the event[^V166]. Infrastructure as code with CDK, public before judging **[team]**.
8. **Stretch: compare runs.** The same task on two models side by side, showing the eval tells them apart[^T190][^V153].

## Decisions

| Area | Decision | Brief says |
| --- | --- | --- |
| Harness | Amazon Bedrock AgentCore + Strands Agents **[team]** | An agent framework, not prescribed, kept swappable[^T86]; agent on Bedrock behind an abstraction[^T105] |
| Models | Claude Sonnet 5.5 and Kimi K3 on Bedrock; Haiku dropped **[team]** | Agent on Bedrock behind an abstraction[^T105] |
| Tools | RODA MCP server + LGND Geo MCP server, which signs in through OAuth in the browser (`harness lgnd-login`) **[team]** | Start with RODA[^T34]; LGND Geo is a commercial server teams are whitelisted for[^T144] |
| Prompts | Find data centers near Dallas, TX, as an open and a strict variant; claims cite one verbatim value from one tool result **[team]** | Teams bring synthetic prompts[^T31] |
| Trace capture | Top priority; OpenTelemetry; covers model decisions **[team]** | Record every step: tool calls, arguments, sequence, failures/retries, latency, cost[^T114] |
| Summary | Generated from the trace **[team]** | Readable summary of what the agent did[^T115] |
| Workflow and output scoring | Generalized rubric, with 2 measured and 8 judged criteria; 5 judges from 5 model families, median vote, same-family recusal, agreement and confidence, and calibration by planted defects **[team]** | Workflow: tool-call correctness and sequencing, error recovery, steps/cost[^T117]; output: quality vs. a rubric[^T118] |
| UI | Team Foundry console on FastAPI with Tabler, MapLibre and vendored assets **[team]** | FastAPI, the thin API behind the UI[^T99]; minimal UI to launch a run and read the report[^V130] |
| Report & replay | Built: a static HTML report per run, offline replay, and a suite comparison table **[team]** | Per-run report[^T119]; replay recorded traces through scoring[^T121] |

## Traceability

Traceability covers the model's **decisions**, not only technical telemetry **[team]**. The brief makes trust and provenance first-class[^V34] and rules out judging on final output alone[^T176]. Every run's trace answers four questions **[team]**:

| Question | What we capture |
| --- | --- |
| What was the model given? | Model ID and version, parameters, system prompt and its version, the full message history at each step, the tools it could use |
| What did it decide, and why? | Its reasoning text where the model exposes it, each tool call and its arguments, and alternatives it rejected or abandoned |
| What did it see? | Each tool's full result or error, retries and their cause, and changes of plan after a failure |
| What is each claim based on? | A link from every dataset, fact or number in the output back to the tool result it came from; unsourced claims are flagged |

Reasoning text is the model's *stated* rationale and may not reflect why it acted **[team]**. Trust rests on the last row, which we call **claim provenance**: if every claim links to a real tool result, the output can be checked whatever the model said **[team]**. (We avoid the word "grounding" for this, because the caption rubric uses it for something else[^V89].)

Inputs and outputs are stored in full, not summarized, so the summary and the replay can rebuild every decision **[team]**.

## OpenTelemetry: the pluggability contract

OpenTelemetry is a must **[team]**. The brief names an OpenTelemetry-based trace approach as a reasonable default[^T88] and says never to hard-wire a tracing vendor[^T177]. Three rules follow **[team]**:

1. **OpenTelemetry is the only contract.** The agent emits OpenTelemetry spans; nothing in our code calls a specific backend. AgentCore/CloudWatch is the deployed backend. Any OpenTelemetry backend, such as Langfuse or Phoenix, can be swapped in as an exporter, and our S3 JSONL archive runs alongside whichever is used.
2. **Decision data lives in the spans.** Prompts, reasoning, tool choices, tool results and claim-provenance links are span attributes and events, following the OpenTelemetry GenAI conventions where they exist. Nothing goes in a side channel, so a backend swap loses nothing.
3. **Replay and the report read OpenTelemetry data.** They work from the stored spans, not a backend's API, so they keep working whichever backend is plugged in.

**The proof:** we decided against a live two-backend demo **[team]**. Instead, an automated test runs the same agent activity through two exporters, changing only config, and checks that both receive the same agent spans **[team]**. This meets the brief's requirement that the tracing tool be demonstrated as swappable[^V164].

## Not doing

- Track 2 (caption generation) before Track 1 works end to end[^T34][^V180] **[team]**.
- Training the Clay model (out of scope)[^V136].
- A data warehouse; a JSONL archive is enough[^T167][^V140]. The console is a local FastAPI app with no build step and no authentication; it binds to 127.0.0.1 **[team]**.
- Running Clay's whole eval backlog; one representative eval proves the loop[^V137].

## Milestones

We build Tuesday 1:00–5:30 pm and Wednesday 9:30 am–5:30 pm. Judging is Thursday at a different building (WAS17, 510 14th St S): prelims 10:00–12:00, DC finals 2:10–2:50 pm. **[event]** (The brief frames it as a 2-day build[^V3].)

The order of the milestones follows the brief: one trace first, then scoring, then the rest[^T34]. Their times, and "roles assigned", are **[team]** and **[event]**.

- [x] **Tue, by 3:00 pm:** sandbox up, Bedrock access checked **[team]**. Still open: ADB's task and rubric from Clay[^V191].
- [x] **Tue, by 5:30 pm:** one agent run captured end to end as an OpenTelemetry trace, decisions included[^T34] **[team]**.
- [x] **Wed, by noon:** trace summary and first report produced[^V162]; workflow signals reported raw, while the output score waits for the rubric **[team]**.
- [x] **Wed, by 5:30 pm:** model swap, exporter-swap test green in CI, replay fallback, CDK and public repo done[^V164][^V165] **[team]**. Demo rehearsal still to do **[team]**.
- [ ] **Thu, 10:00 am–noon:** present in prelims; our slot is announced at 9:15 **[event]**.

## How we win

The four judging criteria are weighted equally, and five other teams have the same brief. **[event]**

| Criterion **[event]** | Our answer |
| --- | --- |
| Technological Implementation | Bedrock[^T105], AgentCore and Strands, OpenTelemetry, S3[^T90] and CDK **[team]**, each named on the architecture slide **[team]** |
| Design | Swappable parts[^T177], with OpenTelemetry as the one contract between the agent and whatever observes it **[team]**; a readable report page[^V130] |
| Potential Impact | Clay and ADB can trust agent-built datasets[^V13] and start working through their eval backlog[^V13][^V19] |
| Quality of Idea | Decision-level traceability with claim provenance **[team]**, an exporter swap proven by test **[team]**, and a side-by-side model comparison[^T190] |

## Open questions

We need the Clay answers before Tuesday's 1:00 pm build start **[event]**; none of them blocks setting up the agent and tracing **[team]**.

**For Clay**

- [ ] Which ADB task should we target, and what input dataset comes with it?[^V191]
- [ ] What does the ADB scoring rubric evaluate: the agent's traces, its output, or both?[^T31][^V191]
- [ ] Is there a harness under test for us to evaluate, or is our agent the one being evaluated?[^V70][^V191]
- [ ] Can we get the geoMCP shortlist? The PDF links it, but we only have the name.[^V189]
- [x] ~~How do we get whitelisted for the LGND Geo MCP server?~~[^T144] Resolved: the browser OAuth login works, and the deployed agent uses LGND Geo **[team]**.
- [ ] How does your existing evaluation harness record results, and should our trace and report formats match it?[^T23]
- [ ] Which observability backend do you use, so we ship an OpenTelemetry exporter for it?[^T10] **[team]**
- [ ] Where should the repo live, and is Apache-2.0 the license you want?[^V33][^V200]

**For the organizers** **[event]**

- [ ] How does the point system announced at kickoff work?
- [x] ~~Which Bedrock models are enabled in the sandbox, and in which regions? Is AgentCore available?~~ Answered by checking us-west-2: Claude (through inference profiles), Kimi K3 and AgentCore are all available **[team]**.
- [ ] How long is each preliminary presentation, and is a live demo allowed?
- [ ] How do we submit: a repo link only, or a form too?
- [ ] Can we use code or templates written before the event?

## Glossary

Every acronym and product name used above, in alphabetical order.

| Term | What it is |
| --- | --- |
| ADB | Asian Development Bank, a Clay partner that needs evals for building datasets with AI[^V13][^V19] |
| AgentCore | Amazon Bedrock AgentCore: AWS services for running agents, with built-in observability that sends OpenTelemetry traces to CloudWatch **[ext]** |
| Apache-2.0 | A permissive open-source license **[ext]**; Clay releases its work under it[^V33] |
| Bedrock | Amazon Bedrock, the AWS service that hosts the AI models our agent calls[^T105] |
| CDK | AWS Cloud Development Kit: infrastructure written as code (Python or TypeScript) **[ext]** |
| Claim provenance | Our check that every dataset, fact or number the agent reports links back to a tool result **[team]** |
| Dossier | The code-built evidence the judges read: task, area, tools, each step and its output, totals and the final answer **[team]** |
| Judge panel | Five LLMs from five model families that score a run against the rubric; the median vote counts **[team]** |
| Krippendorff's α | A chance-corrected measure of agreement between raters; 1 means perfect agreement, 0 means chance **[ext]** |
| Clay | An applied-AI initiative hosted at Renaissance Philanthropy, and our nonprofit for the event **[event]**; also its open Earth-observation foundation model[^T23] |
| Exporter | The OpenTelemetry component that sends traces to a backend; swapping it changes where traces go **[ext]** |
| Harness | The code that runs the agent: its prompts, model and tool connections[^V49] |
| JSONL | JSON Lines: one JSON record per line **[ext]**; the format of our S3 trace archive **[team]** |
| Kimi K3 | Moonshot AI's model on Bedrock (`us.moonshotai.kimi-k3`), our second model **[team]** |
| Langfuse, Phoenix | Open-source tools for viewing and analyzing AI agent traces **[ext]**; candidate backends **[team]** |
| LGND | A company that builds on Clay and publishes Clay embedding datasets[^T139]; it also offers the commercial LGND Geo MCP server for searching Earth data[^T144] |
| MCP | Model Context Protocol, an open standard for connecting AI agents to tools and data[^V50] |
| NAIP | US aerial imagery at 0.3–1 m resolution, on AWS[^T136]; LGND Geo searches it **[team]** |
| OpenTelemetry | An open standard for recording traces, with GenAI conventions for AI model calls **[ext]**; the brief's reasonable default[^T88] |
| RODA | Registry of Open Data on AWS; its MCP server lets the agent search and sample public datasets[^T139] |
| S3 | Amazon Simple Storage Service **[ext]**, where we archive traces and reports **[team]** |
| Sonnet 5.5 | Anthropic's Claude Sonnet 5.5 on Bedrock (`us.anthropic.claude-sonnet-5-5`), our default model **[team]** |
| Span | One timed step in an OpenTelemetry trace, such as a model call or a tool call, with attributes and events **[ext]** |
| Team Foundry | Our team name (Team 46) and the name of the console **[team]** |
| Strands | Strands Agents, an open-source AWS SDK for building agents that emits OpenTelemetry traces **[ext]** |
| Trace | The step-by-step record of a run: each tool call, its inputs and outputs, errors, time and cost[^T114][^V51] |

[^T8]: Technical L8: "observe, summarize, and score agentic geospatial workflows".
[^T9]: Technical L9: "the ADB agentic eval is the recommended starting point".
[^T10]: Technical L10: model on Bedrock behind an abstraction; the team recommends a tracing tool but keeps it swappable.
[^T23]: Technical L23: Clay's open Earth foundation model, an existing evaluation harness.
[^T27]: Technical L27–32: "The Tasks" table lists the ADB agentic eval and caption generation.
[^T31]: Technical L31: ADB task inputs are an input dataset, harness(es) under test and synthetic prompts (teams bring); scored against a rubric; "output is the traces".
[^T34]: Technical L34: start with ADB, Bedrock harness plus RODA MCP, a single trace end to end before scoring, one task before a second.
[^T86]: Technical L86: an agent framework, kept swappable; "framework not prescribed".
[^T88]: Technical L88: "an OpenTelemetry-based LLM trace approach is a reasonable default".
[^T90]: Technical L90: boto3 for S3 and Bedrock access.
[^T105]: Technical L105: Amazon Bedrock for the agent's reasoning, behind an abstraction.
[^T114]: Technical L114: capture tool calls, arguments, sequence, failures/retries, latency, cost.
[^T115]: Technical L115: summarize traces into what the agent did and where it struggled.
[^T99]: Technical L99: FastAPI, "Thin API behind the UI", for launching runs and serving reports.
[^T116]: Technical L116: "Score — two dimensions".
[^T117]: Technical L117: workflow score from traces: tool-call correctness and sequencing, error recovery, steps/cost.
[^T118]: Technical L118: output quality vs. the task's reference, a rubric for ADB.
[^T119]: Technical L119: a per-run evaluation report combining the summary and the scores.
[^T121]: Technical L121: persist traces so recorded runs can be replayed through scoring.
[^T136]: Technical L136: NAIP on AWS, "High-res (0.3–1 m) 4-band US aerial imagery".
[^T139]: Technical L138–139: LGND embeddings at source.coop/clay/lgnd-embeddings; RODA MCP server for Registry of Open Data discovery/sampling.
[^T144]: Technical L144: LGND Geo MCP server, a commercial product; teams are whitelisted for the hackathon.
[^T167]: Technical L167: no full warehouse; lightweight trace/metadata store.
[^T176]: Technical L176: "Never evaluate on final output alone with no trace".
[^T177]: Technical L177: "Never hard-wire a specific model or tracing vendor".
[^T190]: Technical L190: sensitivity analysis, including varying the model.
[^V3]: Vision L3: "guardrails for a 2-day build".
[^V7]: Vision L7: observed, summarized, and scored end to end.
[^V13]: Vision L13: the bottleneck is "knowing whether to trust" an agent; long eval lists never run; ADB needs custom evals.
[^V19]: Vision L19: ADB needs custom evals; Clay's eval backlog is growing.
[^V33]: Vision L33: open and reproducible by default (Apache-2.0).
[^V34]: Vision L34: "Trust and provenance are first-class: every scored run keeps its traces, inputs, and the rubric/reference".
[^V49]: Vision L49: LLM harness, the agent on Bedrock that calls geospatial tools.
[^V50]: Vision L50: MCP tools reached via Model Context Protocol servers.
[^V51]: Vision L51: a trace records tool calls, sequence, failures, cost.
[^V70]: Vision L70: ADB agentic eval, the recommended starting task; evaluate an agent (or set of harnesses); scores the workflow itself.
[^V89]: Vision L89: caption rubric "Grounding": does the caption match what is on the ground.
[^V110]: Vision L110: scored on two dimensions, workflow signals from the traces and output quality vs. a rubric.
[^V113]: Vision L113: tracing tool and model both swappable.
[^V114]: Vision L114: recorded traces replayed to still produce a report.
[^V130]: Vision L130: minimal UI to launch a run and read the report.
[^V136]: Vision L136: training the Clay v2 model is out of scope.
[^V137]: Vision L137: running Clay's entire eval backlog is out of scope.
[^V140]: Vision L140: no full production warehouse stack.
[^V153]: Vision L153–158: stretch sensitivity analysis comparing traces and scores across variants.
[^V162]: Vision L162: end to end: harness, MCP tools, trace capture, summarize, score, report.
[^V164]: Vision L164: tracing tool and model demonstrated as swappable.
[^V165]: Vision L165: recorded-trace fallback verified.
[^V166]: Vision L166: code committed to an open-source repo the Beneficiary can access after the event.
[^V180]: Vision L180: one task fully working first; others are stretch.
[^V189]: Vision L189–190: Clay's free/priority shortlist from Geo-MCP servers ("geoMCP").
[^V191]: Vision L191: ADB task: input data, harness(es), scoring rubric (from Clay).
[^V200]: Vision L200: open-source repo created at kickoff.
