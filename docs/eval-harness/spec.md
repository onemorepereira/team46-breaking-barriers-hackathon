# Track 1 Evaluation Harness — Spec

**Track:** Standard   **Product stage:** Introduction
**Status:** Draft   **Last updated:** 2026-11-03

> References like (T114) or (V34) are lines in the [Technical](../Clay-Foundry-Technical-Hackathon.md) and [Vision](../Clay-Foundry-Vision-Hackathon.md) briefs. **[talk 00:47:27]** is a timestamp in the recording of Clay's kickoff presentation on Nov 3. **[team]** marks our own decisions. **[event]** marks organizer logistics.

## Problem

Clay and ADB can't tell whether to trust a dataset an AI agent built (V13). Nothing records what the agent was given, what it decided, and what each claim in its output rests on, in a form a person or a scorer can inspect (V34, T176). In Clay's words: "We all have ways of doing agentic workflows. What we don't have is an easy way of tracking whether it's working" **[talk 00:47:57]**.

## Users

- **Primary:** Clay's model and data team, and ADB as the partner that needs custom evals (V26, V27). Clay's example of an ADB analyst need is "find the warehouses in Nagoya" **[talk 00:45:07]**. Our task is a sibling of it: find data centers near Dallas, TX **[team]**.
- **Secondary:** LGND engineers, who do this work by hand today and want to know how well an agent does it **[talk 00:45:43]**. Developers of the harness under test, who need to see where a run failed (V28). Hackathon judges, who need to see it working **[event]**.

## Goals

- Every agent run leaves a complete record of the model's decisions, not just timings.
- Anyone can read a run's report without access to the live agent.
- Runs can be compared side by side across tasks and models, which Clay asked for **[talk 00:47:44]**.
- Swapping the observability backend or the model needs no code change.

## Non-goals

- **Caption generation (Track 2)** waits until Track 1 works end to end (T34, V180).
- **The final workflow-scoring method.** It's still open **[team]**. This version reports raw workflow signals and leaves scoring pluggable.
- **The output score itself.** It's blocked on ADB's rubric (V191). This version ships the report section with no score in it.
- **Final prompt wording.** The task is decided, but the exact prompts are still open **[team]**. A draft prompt drives the tests.
- **A UI for launching runs.** A command line plus static report files is enough. The brief's minimal UI is only a "Should Have" (V130).
- **Scores or rankings in the comparison.** The comparison table (AC11) shows raw numbers side by side and doesn't declare a winner **[team]**.
- **Other stretch goals:** multi-agent traces, sensitivity analysis, dynamic MCP discovery (T186–T190).
- **Production hardening:** authentication, multi-tenancy, a data warehouse (T167).

## User stories

- As a Clay reviewer, I want to open one report per run and see what the agent did, why, and what each claim is based on, so that I can decide whether to trust the result.
- As a Clay reviewer, I want to compare several runs on the same tasks, across models, so that I can see which agentic setup does better **[talk 00:47:44]**.
- As a harness developer, I want each step of a run (model call or tool call) with its full inputs and outputs, so that I can find exactly where the run went wrong.
- As a presenter, I want to replay a recorded run into a full report, so that the demo works even if the live agent fails (V114).

## Acceptance criteria

- [ ] **AC1 Run.** Given a prompt file and a config file, when I run `harness run`, then an agent deployed on AgentCore Runtime, calling a Bedrock model, completes the task using the RODA and LGND Geo MCP servers **[team]**. It exits with a run ID, and that run's trace is in the archive.
- [ ] **AC2 Model decisions are traced.** Given any archived run, when the trace checker runs, then the run records:
  - the tools available to the agent, by MCP server, which Clay asked to see **[talk 00:47:34]**;
  - the datasets it accessed, derived from its tool calls.

  Every model-call span records:
  - model ID, parameters, and system-prompt hash;
  - the full input messages and the full output;
  - reasoning text, or `reasoning.available=false`;
  - token usage.

  Every tool-call span records:
  - server and tool name, arguments, and the full result or error;
  - latency and retry number.

  The checker reports zero missing fields.
- [ ] **AC3 OpenTelemetry only.** Given the codebase, when it's searched, then no agent or harness code imports a specific observability backend's SDK. All telemetry leaves as OpenTelemetry spans through exporters chosen in config.
- [ ] **AC4 Exporter swap.** Given the agent's telemetry setup and one scripted agent run, when the test runs it twice, changing only the exporter config (first an OTLP exporter sending to a test OTLP receiver, then an in-memory exporter), then both exporters receive the same **agent spans**: the same count, and the same span kinds (agent, model or tool). The code is unchanged between the two, and the test runs in CI. Agent spans are the spans the agent framework and the harness emit; spans that a backend's own auto-instrumentation adds, such as AWS SDK calls, are excluded. There's no live two-backend demo **[team]**. The deployed runtime uses AgentCore Observability (CloudWatch).
- [ ] **AC5 Archive.** Given any run, whichever backend is configured, then its spans are also written as JSONL to the archive: S3 in AWS, or a local directory in development.
- [ ] **AC6 Claim provenance.** Given a run's final output, then each claim states its value and cites the reference label (for example `T3`) of the tool result it came from. The harness stamps every tool result with a label the model can see, and maps each label to its tool-call span. The report gives each claim one status:
  - **matched:** the cited span is a tool result, and the claimed value appears in that result. Text is compared ignoring case and with whitespace runs collapsed, and values under 3 characters must match a whole word. Numbers are compared as numbers, within the precision the claim states (`32.80` matches `32.8008`).
  - **mismatch:** the cited span is a tool result, but the value doesn't appear in it.
  - **unsourced:** there's no citation, or the cited label doesn't map to a tool result.

  A test fixture with one claim of each kind gets all three statuses right.
- [ ] **AC7 Summary.** Given an archived trace, when the summary is generated, then it lists the run's steps in order and the tools used. It names every **trouble spot**: a step with an error or a retry, and every claim marked mismatch or unsourced (AC6). Every step or claim it mentions links to a span ID that exists in the trace. A fixture trace with known trouble spots gets every one of them named, with no false span IDs.
- [ ] **AC8 Report.** Given a run, then one static report file contains:
  - run metadata (model, prompt version, start and end time);
  - the tools available and the datasets accessed (AC2);
  - the summary;
  - a step-by-step timeline;
  - workflow signals, reported as raw numbers with no score **[team]**: step count, tool calls, errors, retries, tokens, estimated cost, latency, and wall-clock runtime. Clay asked for "how long did it take, how much compute did it use" **[talk 00:47:37]**. Cost is tokens times a price table in config;
  - the claim-provenance table;
  - an output-score section that says "awaiting rubric" until a rubric is configured. The scorer reads a rubric file, so ADB's rubric can be plugged in without code changes **[team]**.
- [ ] **AC9 Replay.** Given an archived run, when I run `harness replay <run-id>` with no access to the agent's model or the MCP servers, then it produces the same report, apart from the generation timestamp. Any summary text written by a model is read back from the archive, not regenerated.
- [ ] **AC10 Model swap.** Given a config change to a different Bedrock model ID, when the same prompt runs, then the trace records the new model ID and the code is unchanged.
- [ ] **AC11 Suite and comparison.** Given a suite file that lists prompts and model configs, when I run `harness run --suite <file>`, then it runs every prompt with every model config. Then `harness compare <suite-id>` produces one static comparison table from the archive. It has one row per run, with:
  - the task and the model;
  - the AC8 workflow signals;
  - the counts of matched, mismatch and unsourced claims;
  - the datasets accessed.

  A suite of 2 prompts and 2 models gives 4 rows. It also works with no live access, like AC9.

## Success signals

- At the Wednesday 5:30 pm rehearsal **[event]**, the replay (AC9) and one comparison table (AC11) are each shown live, once, and the AC4 exporter-swap test is green in CI.
- 100% of the runs recorded before judging pass the trace checker (AC2). Measured as runs that pass divided by runs recorded, from Tuesday's first run until Thursday at 10 am.
- Clay, looking at one report and one comparison table, can answer "can we trust this run?" and "which setup did better?", and point to the evidence. This one is qualitative; we ask them directly.

## Constraints

- Amazon Bedrock for the model, behind an abstraction (T105).
- Agent built with AgentCore + Strands **[team]**.
- OpenTelemetry for all telemetry **[team]**.
- Python 3.12+ (T71).
- A single empty AWS sandbox account (T22). Public or synthetic data only (T12). No services on the brief's disallow list (T165–T168).
- Apache-2.0, in an open-source repo (V33, V166).
- Keep the agent and the problem simple and bounded, as Clay asked **[talk 00:47:57]**.
- Budget capped at $500 in the sandbox **[event]**.
- Done by Wednesday 5:30 pm **[event]**.

## Assumptions and open questions

**Decided**
- Workflow scoring reports raw signals only in this version (AC8). The scoring method is still open. *Owner:* Miguel.
- No live backend-swap demo, and no Phoenix **[team]**. Pluggability is proven by the AC4 test. The deployed backend is AgentCore Observability.
- The agent runs on AgentCore Runtime from day 1 (AC1).
- Claim provenance checks values, not just citations (AC6).
- This version includes run comparison (AC11), as raw numbers only.
- **The task: find data centers near Dallas, TX** **[team]**. Clay named "which are likely to be data centers" as one of the queries in this task family **[talk 00:49:28]**.
- The rubric stays open. The data-resolution question (A6) is deferred.

**Assumptions**
- **A1:** Strands emits OpenTelemetry spans for model and tool calls, including prompts, tool arguments and tool results. *If it doesn't,* we add our own instrumentation. *Check:* a Design spike against the docs for the pinned version.
- **A2:** AgentCore Observability takes standard OpenTelemetry and doesn't block a second exporter. *If it does,* the archive exporter runs inside the agent process. *Check:* Design spike.
- **A3:** a Bedrock model that returns its reasoning is enabled in the sandbox. *If not,* we record `reasoning.available=false`, and claim provenance (AC6) carries the trust case. *Check:* organizers, on Tuesday.
- **A4:** LGND Geo whitelisting arrives by Tuesday afternoon. *If not,* AC1 runs with RODA only, and LGND Geo is added when access arrives. *Owner:* Miguel, with Clay.
- **A5:** AgentCore Runtime is available in the sandbox and supports MCP servers launched over stdio, which is how RODA runs (`uvx`, T34). *If not,* RODA runs as a separate hosted MCP endpoint. *Check:* Design spike, plus the organizers on Tuesday.
- **A6 (deferred):** the data the agent can reach is detailed enough for the task. The Clay embeddings on Source Cooperative are monthly, built on Sentinel imagery, and end about a year ago **[talk 00:17:51]**. We believe Sentinel-2 is about 10 m resolution, which may be too coarse to find individual buildings (unverified). *If it's too coarse,* we pick a task at a coarser scale, or use finer data the LGND server offers. *Check:* Clay, in the working session. *Note:* Dallas is in the US, so NAIP's 0.3–1 m aerial imagery is available (T137), which may settle this.
- **A7:** Clay accepts a US task as a fair stand-in for ADB's work, even though ADB's focus is Asia **[talk 00:13:55]**. *If not,* we keep the harness unchanged and only change the prompt and the answer key. *Check:* Clay, in the working session.

**Open**
- **ADB's input dataset and rubric for the task.** Clay offered to shape these with each team one-on-one **[talk 00:51:55]**. *Owner:* Miguel, with Deepa and Kinzah. *Default:* the rubric stays open and the output score says "awaiting rubric".
- **The prompt wording.** *Owner:* Miguel. *Default:* one draft prompt, "Find the data centers near Dallas, TX, and list each one with its location and the evidence for it", plus one variant for the AC11 suite.
- **What "near Dallas" means.** The bound decides what counts as a correct answer. *Owner:* Miguel. *Default:* within 50 km of downtown Dallas.
- **The answer key.** *Owner:* Miguel. *Default:* OpenStreetMap features tagged as data centers within the bound. OSM is a listed data source (T143). We believe OSM has a data-center tag, but haven't checked it or how complete the Dallas coverage is (unverified).
- **The rubric file format and how it's scored.** *Owner:* Miguel. *Default:* a list of criteria, each with a question, scored by a pluggable evaluator. Nothing is scored until a rubric is configured.
- **Decided (Design):** claims cite tool-result labels such as `T3`, not raw IDs. A test showed the model can't see Bedrock's `toolUseId`, but it reliably repeats a label printed in the tool result.
- **Is the summary written by an LLM or generated by code?** *Owner:* Miguel. *Default:* the timeline is generated by code, the narrative by an LLM, and the narrative is saved with the run so replay doesn't need the model.
