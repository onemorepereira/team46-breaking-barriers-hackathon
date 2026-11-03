# Team 46 Manifest — Clay Earth Dataset Foundry

Nov 3, 2026 · @Miguel

> **Sources.** Each statement cites where it comes from. Most cite the two briefs, [Technical](docs/Clay-Foundry-Technical-Hackathon.md) (T) and [Vision](docs/Clay-Foundry-Vision-Hackathon.md) (V), with line numbers. Both briefs include Clay's suggested edits from [the Nov 3 PDF](<docs/suggested hackathon edits.pdf>). Statements that are not in either brief carry a tag instead: **[team]** for our own decisions, **[event]** for event logistics from the organizers, and **[ext]** for general background.

## Mission

Build an open-source sandbox that **observes, summarizes and scores** an AI agent doing a geospatial dataset task[^T8][^V7], so Clay and ADB can tell whether to trust what the agent built[^V13].

## Scope: Track 1, the ADB agentic eval

The briefs now offer two tasks, the ADB agentic eval and caption generation[^T27]; the open third track was removed in the Nov 3 edits **[event]**. We focus on **Track 1, the ADB agentic eval**, which both briefs name as the starting point[^T9][^V70] **[team]**. Caption generation (Track 2) is out unless Track 1 works end to end first[^T34][^V180] **[team]**.

Track 1 evaluates an agent doing an ADB-style "how to use AI / build datasets" task. Its inputs are an input dataset, the harness(es) under test and synthetic prompts that teams bring; it is scored against a rubric, and its output is the traces gathered from observing the system[^T31][^V70]. The task, the dataset and the rubric come from Clay[^V191].

## Goals

1. **One loop, end to end.** An agent calls geospatial tools over MCP, and every run ends in a report[^T34][^V162].
2. **Trace everything, including the model's decisions.** Trace capture is our top priority **[team]**. Every run keeps its traces and inputs[^V34], and never gets judged on its final output alone[^T176]. See [Traceability](#traceability).
3. **Summarize the run.** A readable account, generated from the trace, of what the agent did and where it struggled[^T115].
4. **Score two things.** The workflow, from the traces[^T117]; the output, against ADB's rubric[^T31]. How we score the workflow is still **open** **[team]**.
5. **Keep observation pluggable.** The model and the tracing tool both stay swappable[^T10][^V113]. OpenTelemetry is the linchpin that proves it: a CI test sends the same agent spans to two different exporters, changing only config **[team]**. See [OpenTelemetry](#opentelemetry-the-pluggability-contract).
6. **Never fail the demo.** Recorded traces replay through the scorer and still produce a full report[^T121][^V114].
7. **Ship it open.** Apache-2.0[^V33], in an open-source repo Clay can access after the event[^V166]. Infrastructure as code with CDK, public before judging **[team]**.
8. **Stretch: compare runs.** The same task on two models side by side, showing the eval tells them apart[^T190][^V153].

## Decisions

| Area | Decision | Brief says |
| --- | --- | --- |
| Harness | Amazon Bedrock AgentCore + Strands Agents **[team]** | An agent framework, not prescribed, kept swappable[^T86]; agent on Bedrock behind an abstraction[^T105] |
| Tools | RODA MCP server + LGND Geo MCP server **[team]** | Start with RODA[^T34]; LGND Geo is a commercial server teams are whitelisted for[^T144] |
| Prompts | **Open** **[team]** | Teams bring synthetic prompts[^T31] |
| Trace capture | Top priority; OpenTelemetry; covers model decisions **[team]** | Record every step: tool calls, arguments, sequence, failures/retries, latency, cost[^T114] |
| Summary | Generated from the trace **[team]** | Readable summary of what the agent did[^T115] |
| Workflow scoring | **Open** **[team]** | Tool-call correctness and sequencing, error recovery, steps/cost[^T117] |
| Report & replay | Ours to build; no dependency on Clay **[team]** | Per-run report[^T119]; replay recorded traces through scoring[^T121] |

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
- A heavy UI or a data warehouse; a thin report page is enough[^T167][^V130][^V140].
- Running Clay's whole eval backlog; one representative eval proves the loop[^V137].

## Milestones

We build Tuesday 1:00–5:30 pm and Wednesday 9:30 am–5:30 pm. Judging is Thursday at a different building (WAS17, 510 14th St S): prelims 10:00–12:00, DC finals 2:10–2:50 pm. **[event]** (The brief frames it as a 2-day build[^V3].)

The order of the milestones follows the brief: one trace first, then scoring, then the rest[^T34]. Their times, and "roles assigned", are **[team]** and **[event]**.

- [ ] **Tue, by 3:00 pm:** sandbox up, Bedrock access checked, roles assigned, ADB task and rubric agreed with Clay[^V191].
- [ ] **Tue, by 5:30 pm:** one agent run captured end to end as an OpenTelemetry trace, decisions included[^T34] **[team]**.
- [ ] **Wed, by noon:** trace summary and both scores working; first report produced[^V162].
- [ ] **Wed, by 5:30 pm:** model swap, exporter-swap test green, replay fallback, CDK and public repo done; demo rehearsed[^V164][^V165].
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
- [ ] How do we get whitelisted for the LGND Geo MCP server?[^T144]
- [ ] How does your existing evaluation harness record results, and should our trace and report formats match it?[^T23]
- [ ] Which observability backend do you use, so we ship an OpenTelemetry exporter for it?[^T10] **[team]**
- [ ] Where should the repo live, and is Apache-2.0 the license you want?[^V33][^V200]

**For the organizers** **[event]**

- [ ] How does the point system announced at kickoff work?
- [ ] Which Bedrock models are enabled in the sandbox, and in which regions? Is AgentCore available?
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
| Clay | An applied-AI initiative hosted at Renaissance Philanthropy, and our nonprofit for the event **[event]**; also its open Earth-observation foundation model[^T23] |
| Exporter | The OpenTelemetry component that sends traces to a backend; swapping it changes where traces go **[ext]** |
| Harness | The code that runs the agent: its prompts, model and tool connections[^V49] |
| JSONL | JSON Lines: one JSON record per line **[ext]**; the format of our S3 trace archive **[team]** |
| Langfuse, Phoenix | Open-source tools for viewing and analyzing AI agent traces **[ext]**; candidate backends **[team]** |
| LGND | A company that builds on Clay and publishes Clay embedding datasets[^T139]; it also offers the commercial LGND Geo MCP server for searching Earth data[^T144] |
| MCP | Model Context Protocol, an open standard for connecting AI agents to tools and data[^V50] |
| OpenTelemetry | An open standard for recording traces, with GenAI conventions for AI model calls **[ext]**; the brief's reasonable default[^T88] |
| RODA | Registry of Open Data on AWS; its MCP server lets the agent search and sample public datasets[^T139] |
| S3 | Amazon Simple Storage Service **[ext]**, where we archive traces and reports **[team]** |
| Span | One timed step in an OpenTelemetry trace, such as a model call or a tool call, with attributes and events **[ext]** |
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
[^T117]: Technical L117: workflow score from traces: tool-call correctness and sequencing, error recovery, steps/cost.
[^T119]: Technical L119: a per-run evaluation report combining the summary and the scores.
[^T121]: Technical L121: persist traces so recorded runs can be replayed through scoring.
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
