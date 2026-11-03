# Team 46 Manifest — Clay Earth Dataset Foundry

Nov 3, 2026 · @Miguel

> **Sources.** Each statement cites where it comes from. Most cite the two briefs, [Technical](docs/Clay-Foundry-Technical-Hackathon.md) (T) and [Vision](docs/Clay-Foundry-Vision-Hackathon.md) (V), with line numbers. Statements that are not in either brief carry a tag instead: **[team]** for our own decisions, **[event]** for event logistics from the organizers, and **[ext]** for general background.

## Mission

Build an open-source sandbox that **observes, summarizes and scores** an AI agent doing a geospatial dataset task[^T8][^V7], so Clay and ADB can tell whether to trust what the agent built[^V13].

## Goals

1. **One loop, end to end.** A Bedrock agent runs the ADB-style task through MCP tools (RODA first), and every run ends in a report.[^T35][^V66][^V83]
2. **Capture every trace.** Tool calls, arguments, order, failures, cost and latency[^T86]; we also record tokens, saved to S3 as JSONL **[team]**.
3. **Summarize the run.** A readable account of what the agent did and where it struggled. This is Clay's explicit ask.[^T87]
4. **Score two things.** The workflow, from the traces; the output, against Clay's rubric.[^T88] Our own trace rubric (grounding first) and our approved draft as a fallback reference are **[team]**.
5. **Keep parts swappable.** The model and the tracing tool both sit behind interfaces.[^T10][^T92] We prove it by switching them live **[team]**; the brief asks only that both be demonstrated as swappable[^V134].
6. **Never fail the demo.** Recorded traces replay through the scorer and still produce a full report.[^T13][^V85]
7. **Ship it open.** Apache-2.0[^V33], in an open-source repo Clay can access after the event[^V136]. Infrastructure as code with CDK, public before judging **[team]**.
8. **Stretch: compare runs.** The same task on two models side by side, showing the eval tells them apart.[^T143][^V123]

## Not doing

- Training the Clay model (out of scope)[^V106]; for captions we reuse Clay's published embeddings instead of running the model[^T70].
- A second task before the first one works end to end.[^T35][^V150]
- A heavy UI or a data warehouse; a thin report page is enough.[^T120][^V100][^V110]
- Bulk NAIP pulls; we use a small pre-staged sample[^T102][^V149] (the sandbox is capped at $500 **[event]**).

## Milestones

We build Tuesday 1:00–5:30 pm and Wednesday 9:30 am–5:30 pm. Judging is Thursday at a different building (WAS17, 510 14th St S): prelims 10:00–12:00, DC finals 2:10–2:50 pm. **[event]** (The brief frames it as a 2-day build[^V3].)

The order of the milestones follows the brief: one trace first, then scoring, then the rest[^T35]. Their times, and "roles assigned", are **[team]** and **[event]**.

- [ ] **Tue, by 3:00 pm:** sandbox up, Bedrock access checked, roles assigned, ADB task and rubric agreed with Clay[^V167].
- [ ] **Tue, by 5:30 pm:** one agent run captured as a trace end to end[^T35].
- [ ] **Wed, by noon:** trace summary and both scores working; first report produced[^V132].
- [ ] **Wed, by 5:30 pm:** model swap, replay fallback, CDK and public repo done; demo rehearsed[^V134][^V135].
- [ ] **Thu, 10:00 am–noon:** present in prelims; our slot is announced at 9:15 **[event]**.

## How we win

The four judging criteria are weighted equally, and five other teams have the same brief. **[event]**

| Criterion **[event]** | Our answer |
| --- | --- |
| Technological Implementation | Bedrock[^T78], S3[^T64], a serverless runtime[^T22] and CDK **[team]**, each named on the architecture slide **[team]** |
| Design | A clean architecture with swappable parts[^T130], and a readable report page[^V100] |
| Potential Impact | Clay and ADB can trust agent-built datasets[^V13] and start working through their eval backlog[^V13][^V19] |
| Quality of Idea | Trace scoring with grounding checks **[team]**, plus a side-by-side model comparison[^T143] |

## Open questions

We need the Clay answers before Tuesday's 1:00 pm build start **[event]**; none of them blocks setting up the agent and tracing[^V164].

**For Clay**

- [ ] What does the ADB scoring rubric evaluate, and does it score the agent's traces or only its output?[^T31][^V167]
- [ ] Which single ADB task should we target, and what input data comes with it?[^V158][^V167]
- [ ] Is there an agent or harness for us to evaluate, or do we build our own? Who is the co-listed agent partner (is "Legend" LGND)?[^V170]
- [ ] Which MCP servers from the \~99 are on the free and priority shortlist?[^V166]
- [ ] How does your existing evaluation harness record results, and should our trace and report formats match it?[^T23]
- [ ] Do you prefer a tracing tool (Langfuse, Phoenix **[team]**, OpenTelemetry[^T62]), or is our recommendation fine?[^T10]
- [ ] For captions: where are the example captions and the retrieval evaluation set?[^V168]
- [ ] Should we pre-stage a small NAIP sample, or pull live from the Requester-Pays buckets?[^V169]
- [ ] Where should the repo live, and is Apache-2.0 the license you want?[^V33][^V160]

**For the organizers** **[event]**

- [ ] How does the point system announced at kickoff work?
- [ ] Which Bedrock models are enabled in the sandbox, and in which regions?
- [ ] How long is each preliminary presentation, and is a live demo allowed?
- [ ] How do we submit: a repo link only, or a form too?
- [ ] Can we use code or templates written before the event?

## Glossary

Every acronym and product name used above, in alphabetical order.

| Term | What it is |
| --- | --- |
| ADB | Asian Development Bank, a Clay partner that needs evals for building datasets with AI[^V13][^V19] |
| Apache-2.0 | A permissive open-source license **[ext]**; Clay releases its work under it[^V33] |
| Bedrock | Amazon Bedrock, the AWS service that hosts the AI models our agent calls[^T78] |
| CDK | AWS Cloud Development Kit: infrastructure written as code (Python or TypeScript) **[ext]** |
| Clay | An applied-AI initiative hosted at Renaissance Philanthropy, and our nonprofit for the event **[event]**; also its open Earth-observation foundation model[^T23] |
| Embeddings | Lists of numbers that capture what an image shows, so similar images can be found **[ext]**; Clay publishes them openly[^T23] |
| Grounding | Our check that every dataset or fact the agent reports actually came back from a tool call **[team]** |
| Harness | The code that runs the agent: its prompts, model and tool connections[^V49] |
| JSONL | JSON Lines: one JSON record per line **[ext]**; our trace file format **[team]** |
| Langfuse, Phoenix | Open-source tools for viewing and analyzing AI agent traces; candidate tracing tools **[ext]** |
| LGND | A company (lgnd.ai) that builds on Clay **[ext]** and publishes Clay embedding datasets[^T110][^V170] |
| MCP | Model Context Protocol, an open standard for connecting AI agents to tools and data[^V50] |
| NAIP | National Agriculture Imagery Program: high-resolution US aerial imagery, hosted on AWS[^T108]; free, from the USDA **[ext]** |
| OpenTelemetry | An open standard for recording traces, with conventions for AI model calls **[ext]**; a reasonable default per the brief[^T62] |
| Requester-Pays | An S3 setting where whoever downloads the data pays the transfer cost **[ext]**; NAIP uses it[^T108] |
| RODA | Registry of Open Data on AWS; its MCP server lets the agent search and sample public datasets[^T111] |
| S3 | Amazon Simple Storage Service **[ext]**, where we store traces and reports **[team]** |
| Trace | The step-by-step record of a run: each tool call, its inputs and outputs, errors, time and cost[^T86][^V51] |

[^T8]: Technical L8: "observe, summarize, and score agentic geospatial workflows".
[^T10]: Technical L10: model on Bedrock behind an abstraction; the team recommends a tracing tool but keeps it swappable.
[^T13]: Technical L13: recorded traces are replayed through the scoring sandbox for the demo.
[^T22]: Technical L22: "Flexible (serverless / containers / K8s), single sandbox account."
[^T23]: Technical L23: Clay's open Earth foundation model, 15.2B published embeddings (Apache-2.0), an existing evaluation harness.
[^T31]: Technical L31: ADB task scores against a "Scoring rubric; output is the traces".
[^T35]: Technical L35: start with ADB, Bedrock harness plus RODA MCP, a single trace end to end before scoring, one task before a second.
[^T62]: Technical L62: "an OpenTelemetry-based LLM trace approach is a reasonable default".
[^T64]: Technical L64: boto3 for S3 and Bedrock access.
[^T70]: Technical L70: Clay/LGND embeddings, "Reuse rather than train".
[^T78]: Technical L78: Amazon Bedrock for the agent's reasoning, behind an abstraction.
[^T86]: Technical L86: capture tool calls, arguments, sequence, failures/retries, latency, cost.
[^T87]: Technical L87: summarize traces; Clay's explicit ask.
[^T88]: Technical L88–90: score workflow (from traces) and output (vs. rubric).
[^T92]: Technical L92: tracing tool and model both behind an abstraction.
[^T102]: Technical L102: NAIP is Requester-Pays in us-west-2; pre-stage a small sample.
[^T108]: Technical L108: NAIP high-res US aerial imagery on AWS, Requester-Pays.
[^T110]: Technical L110: LGND embeddings at source.coop/clay/lgnd-embeddings.
[^T111]: Technical L111: RODA MCP server for Registry of Open Data discovery/sampling.
[^T120]: Technical L120: no full warehouse; lightweight trace/metadata store.
[^T130]: Technical L130: model and tracing tool behind abstractions.
[^T143]: Technical L143: sensitivity analysis, including varying the model.
[^V3]: Vision L3: "guardrails for a 2-day build".
[^V7]: Vision L7: observed, summarized, and scored end to end.
[^V13]: Vision L13: the bottleneck is "knowing whether to trust" an agent; long eval lists never run; ADB needs custom evals.
[^V19]: Vision L19: ADB needs custom evals; Clay's eval backlog is growing.
[^V33]: Vision L33: open and reproducible by default (Apache-2.0).
[^V49]: Vision L49: LLM harness, the agent on Bedrock that calls geospatial tools.
[^V50]: Vision L50: MCP tools; Clay maintains ~99 servers.
[^V51]: Vision L51: a trace records tool calls, sequence, failures, cost.
[^V66]: Vision L66: ADB agentic eval, the recommended starting task.
[^V83]: Vision L83: the sandbox produces an evaluation report for the run.
[^V85]: Vision L85: recorded traces replayed to still produce a report.
[^V100]: Vision L100: minimal UI to launch a run and read the report.
[^V106]: Vision L106: training the Clay v2 model is out of scope.
[^V110]: Vision L110: no full production warehouse stack.
[^V123]: Vision L123–127: stretch sensitivity analysis comparing traces and scores across variants.
[^V132]: Vision L132: end to end, harness to MCP to trace to summarize to score to report.
[^V134]: Vision L134: tracing tool and model demonstrated as swappable.
[^V135]: Vision L135–136: recorded-trace fallback verified; code in an open-source repo.
[^V136]: Vision L136: code committed to an open-source repo the Beneficiary can access after the event.
[^V149]: Vision L149: pre-stage a small NAIP sample.
[^V150]: Vision L150: one task fully working first.
[^V158]: Vision L158: ADB input data, harness(es), scoring rubric from Clay.
[^V160]: Vision L160: open-source repo created at kickoff.
[^V164]: Vision L164: none of the kickoff questions block starting the ADB eval.
[^V166]: Vision L166: free/priority MCP servers from Clay's ~99.
[^V167]: Vision L167: ADB scoring rubric and one representative eval to target.
[^V168]: Vision L168: example captions and retrieval evaluation set.
[^V169]: Vision L169: NAIP Requester-Pays, pre-staged sample vs. live pull.
[^V170]: Vision L170: co-listed agent partner; "Legend" may be LGND.
