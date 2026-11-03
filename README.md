# Team 46 Manifest — Clay Earth Dataset Foundry

Nov 3, 2026 · @Miguel

## Mission

Build an open-source sandbox that **observes, summarizes and scores** an AI agent doing a geospatial dataset task, so Clay and ADB can tell whether to trust what the agent built.

## Goals

1. **One loop, end to end.** A Bedrock agent runs the ADB-style task through MCP tools (RODA first), and every run ends in a report.
2. **Capture every trace.** Tool calls, arguments, order, failures, tokens, cost and latency, saved to S3 as JSONL.
3. **Summarize the run.** A readable account of what the agent did and where it struggled. This is Clay's explicit ask.
4. **Score two things.** The workflow, from the traces (our trace rubric, grounding first). The output, against Clay's rubric or our approved draft.
5. **Keep parts swappable.** The model and the tracing tool both sit behind interfaces. We prove it by switching them live.
6. **Never fail the demo.** Recorded traces replay through the scorer and still produce a full report.
7. **Ship it open.** Infrastructure as code (CDK), Apache-2.0, in a public repo before judging.
8. **Stretch: compare runs.** The same task on two models side by side, showing the eval tells them apart.

## Not doing

- Training the Clay model (out of scope); for captions we reuse Clay's published embeddings instead of running the model.
- A second task before the first one works end to end.
- A heavy UI or a data warehouse; a thin report page is enough.
- Bulk NAIP pulls; we use a small pre-staged sample (the sandbox is capped at $500).

## Milestones

We build Tuesday 1:00–5:30 pm and Wednesday 9:30 am–5:30 pm. Judging is Thursday at a different building (WAS17, 510 14th St S): prelims 10:00–12:00, DC finals 2:10–2:50 pm.

- [ ] **Tue, by 3:00 pm:** sandbox up, Bedrock access checked, roles assigned, ADB task and rubric agreed with Clay.
- [ ] **Tue, by 5:30 pm:** one agent run captured as a trace end to end.
- [ ] **Wed, by noon:** trace summary and both scores working; first report produced.
- [ ] **Wed, by 5:30 pm:** model swap, replay fallback, CDK and public repo done; demo rehearsed.
- [ ] **Thu, 10:00 am–noon:** present in prelims; our slot is announced at 9:15.

## How we win

The four judging criteria are weighted equally, and five other teams have the same brief.

| Criterion | Our answer |
| --- | --- |
| Technological Implementation | Bedrock, S3, a serverless runtime and CDK, each named on the architecture slide |
| Design | A clean architecture with swappable parts, and a readable report page |
| Potential Impact | Clay and ADB can trust agent-built datasets and run their eval backlog |
| Quality of Idea | Trace scoring with grounding checks, plus a side-by-side model comparison |

## Open questions

We need the Clay answers before Tuesday's 1:00 pm build start; none of them blocks setting up the agent and tracing.

**For Clay**

- [ ] What does the ADB scoring rubric evaluate, and does it score the agent's traces or only its output?
- [ ] Which single ADB task should we target, and what input data comes with it?
- [ ] Is there an agent or harness for us to evaluate, or do we build our own? Who is the co-listed agent partner (is "Legend" LGND)?
- [ ] Which MCP servers from the \~99 are on the free and priority shortlist?
- [ ] How does your existing evaluation harness record results, and should our trace and report formats match it?
- [ ] Do you prefer a tracing tool (Langfuse, Phoenix, OpenTelemetry), or is our recommendation fine?
- [ ] For captions: where are the example captions and the retrieval evaluation set?
- [ ] Should we pre-stage a small NAIP sample, or pull live from the Requester-Pays buckets?
- [ ] Where should the repo live, and is Apache-2.0 the license you want?

**For the organizers**

- [ ] How does the point system announced at kickoff work?
- [ ] Which Bedrock models are enabled in the sandbox, and in which regions?
- [ ] How long is each preliminary presentation, and is a live demo allowed?
- [ ] How do we submit: a repo link only, or a form too?
- [ ] Can we use code or templates written before the event?

## Glossary

Every acronym and product name used above, in alphabetical order.

| Term | What it is |
| --- | --- |
| ADB | Asian Development Bank, a Clay partner that needs evals for building datasets with AI |
| Apache-2.0 | A permissive open-source license; Clay releases its work under it |
| Bedrock | Amazon Bedrock, the AWS service that hosts the AI models our agent calls |
| CDK | AWS Cloud Development Kit: infrastructure written as code (Python or TypeScript) |
| Clay | An applied-AI initiative hosted at Renaissance Philanthropy, and its open Earth-observation foundation model; our nonprofit for the event |
| Embeddings | Lists of numbers that capture what an image shows, so similar images can be found; Clay publishes them for free |
| Grounding | Our check that every dataset or fact the agent reports actually came back from a tool call |
| Harness | The code that runs the agent: its prompts, model and tool connections |
| JSONL | JSON Lines: one JSON record per line, our trace file format |
| Langfuse, Phoenix | Open-source tools for viewing and analyzing AI agent traces; candidate tracing tools |
| LGND | A company (lgnd.ai) that builds on Clay and publishes Clay embedding datasets |
| MCP | Model Context Protocol, an open standard for connecting AI agents to tools and data |
| NAIP | National Agriculture Imagery Program: free high-resolution US aerial imagery from the USDA, hosted on AWS |
| OpenTelemetry | An open standard for recording traces, with conventions for AI model calls |
| Requester-Pays | An S3 setting where whoever downloads the data pays the transfer cost; NAIP uses it |
| RODA | Registry of Open Data on AWS; its MCP server lets the agent search and sample public datasets |
| S3 | Amazon Simple Storage Service, where we store traces and reports |
| Trace | The step-by-step record of a run: each tool call, its inputs and outputs, errors, time and cost |
