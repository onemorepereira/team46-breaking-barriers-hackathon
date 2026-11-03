# Track 1 Evaluation Harness — Design

**Spec:** ./spec.md   **Last updated:** 2026-11-03
**Status:** Ready for planning (revision 6: pass-5 blocking issues fixed but not re-reviewed; Phoenix and the live swap demo dropped)

Verified facts carry a source; anything else is marked **(unverified, spike S#)**. **Tested** means we ran it against the sandbox (account 892605951158, us-west-2, 2026-11-03).

## Overview

The harness has three parts.

1. **The agent.** A Strands agent on AgentCore Runtime calls a Bedrock model and two MCP servers.
2. **The decision record.** Strands hooks in the agent record every decision as our own small `harness.*` spans: the tools available, each model result with its reasoning, and each tool call with its arguments, result and reference label. These spans don't depend on what Strands or the backend happen to record.
3. **The archive and analysis.** A span processor serializes every span to JSONL in S3 at the moment the span ends. A local analysis package reads only that archive.

The deployed runtime sends telemetry to AgentCore Observability (CloudWatch). The exporter is chosen by config, and a CI test proves that swapping it needs no code change (AC4). Replay is the same as analysis: it never touches the agent, the model or the MCP servers.

## Experience (CLI)

One command, `harness`, configured by `harness.yaml`. Its outputs go to `out/<run-id>/`.

| Command | Does | Success output | Error output (exact copy) |
| --- | --- | --- | --- |
| `harness run --prompt <file> [--model <key>] [--backend agentcore\|local]` | Invokes the runtime (or the local agent), waits up to 15 minutes, writes `run.json`, the summary and the report | `run 3f2c… done: 14 steps, 2 errors, claims 5 matched / 1 mismatch / 0 unsourced → out/3f2c…/report.html` | `run 3f2c… failed: <reason>. Partial trace archived; run 'harness replay 3f2c…' to see what happened.` |
| `harness run --suite <file>` | Runs every prompt × model one after another. Refuses suites over `max_runs_per_suite` (default 8) | `suite dallas-dc-v1-20261104T1012 done: 4/4 runs → harness compare dallas-dc-v1-20261104T1012` | `suite has 12 runs; max_runs_per_suite is 8. Shrink the suite or raise the limit in harness.yaml.` |
| `harness replay <run-id>` | Rebuilds the report from the archive only | `replayed 3f2c… → out/3f2c…/report.html` | `no archive for run 3f2c… under <archive_uri>/runs/. Check the run ID or archive_uri in harness.yaml.` |
| `harness run --suite` over budget | Refuses before any run | — | `suite worst case $72.40 exceeds max_suite_usd $50. Shrink the suite or raise max_suite_usd in harness.yaml.` |
| `harness compare <suite-id>` | Reads the suite manifest and builds the table | `→ out/<suite-id>/compare.html (4 rows), compare.csv` | `no suite manifest at <archive_uri>/suites/<suite-id>/suite.json.` |
| `harness check <run-id>` | The AC2 trace checker | `3f2c…: 0 missing fields` (exits 0) | `3f2c…: 3 missing fields:` then one line per field: `span <id> (<kind>): <field>` (exits 1) |

States:
- **Partial run.** The report shows a banner, "Run ended early: <reason>". Every span that ended is shown.
- **No narrative.** The report notes "Narrative unavailable; timeline below is complete".
- **No rubric configured.** The output-score section says "awaiting rubric".
- **Rubric configured, no scorer.** The section lists each criterion as "not scored (no evaluator configured)".

## Architecture

```
 harness CLI (local) ─ invoke_agent_runtime ─▶ runtime "agent-agentcore" (arm64 image)
   │  writes run.json, suite.json             (or --backend local: same agent, in a subprocess)
   │                                            boot.sh → agent.main
   │                                            Strands Agent ─ BedrockModel (inference profile)
   │                                              ├ MCPClient stdio: uvx awslabs.roda-mcp-server@0.1.7
   │                                              ├ MCPClient HTTP:  https://geo.lgnd.ai/mcp
   │                                              └ HarnessHooks: refs, decision spans, limits
   │                                            TracerProvider (global)
   │                                              ├ RunContextProcessor.on_start  (run-level attributes)
   │                                              ├ ArchiveProcessor.on_end       (serialize now → buffer → S3)
   │                                              └ exporter: ADOT→CloudWatch | OTLP | console (ADR-1)
   └─ reads <archive_uri>/runs/<id>/, suites/<id>/ ─▶ analysis: check · provenance · signals · score ·
                                                       summary · report · compare
```

| Component | Code | Role |
| --- | --- | --- |
| `agent/` | `boot.sh`, `main.py`, `telemetry.py`, `hooks.py`, `archive.py`, `prompts/system.md` | Container for AgentCore Runtime: HTTP on port 8080 at `/invocations` and `/ping`, on an **ARM64** platform ([HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html), accessed 2026-11-03) |
| `harness/` | `cli.py`, `config.py`, `invoke.py`, `manifest.py` | Local CLI. Owns `run.json` and `suite.json` |
| `analysis/` | `trace.py`, `check.py`, `provenance.py`, `signals.py`, `datasets.py`, `score.py`, `summary.py`, `report.py`, `compare.py` | Pure functions over archived spans plus `run.json`. Imports nothing from `agent/` |
| `infra/` | CDK (Python) | Bucket, ECR asset, role, one runtime, budget, tags |
| `tests/` | pytest + JSONL fixtures | Unit tests; live smoke scripts under `tests/live/` |
| CI | GitHub Actions | pytest, the import-lint test, and the gitleaks action on every push and PR |

### Agent internals

**Boot.** `boot.sh` is the image's single `CMD`:
- `HARNESS_EXPORTER=adot`: `exec opentelemetry-instrument python -m agent.main`, the ADOT path ([observability guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html), accessed 2026-11-03).
- Any other value: `exec python -m agent.main`.

**Tracer provider.**
- *`adot`:* ADOT installs the global provider. `telemetry.py` gets it with `trace.get_tracer_provider()` and calls `add_span_processor()` for our two processors. Whether ADOT's provider is the SDK `TracerProvider` with that method is **(unverified, S2)**.
- *`otlp`, `console`:* `telemetry.py` builds an SDK `TracerProvider` with an always-on sampler, and adds, in order:
  1. `RunContextProcessor`
  2. `ArchiveProcessor`
  3. The configured exporter:
     - `otlp`: a `BatchSpanProcessor` with `opentelemetry-exporter-otlp-proto-http`, configured only by the standard `OTEL_EXPORTER_OTLP_*` variables.
     - `console`: a `SimpleSpanProcessor` with the standard `ConsoleSpanExporter`, writing one JSON span per line to the file in `HARNESS_CONSOLE_PATH`, or to **stderr** by default, never stdout. Strands' docs show `ConsoleSpanExporter` taking an output stream ([Strands traces](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/)).
- *All modes:* `telemetry.py` calls `trace.set_tracer_provider(provider)` once, then `StrandsTelemetry(tracer_provider=provider)`. **S1 showed that Strands' tracer reads the global provider**: passing the provider alone captured zero spans ([spikes.md](spikes.md)). The provider is ([Strands traces](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/), accessed 2026-11-03).
- `HarnessHooks` emits its `harness.*` spans from `provider.get_tracer("harness")` on that **same explicit provider** object, never from the global `trace.get_tracer()`.
- There is exactly one provider per process: `telemetry.py` sets it up once at start-up and never replaces it. Tests that need a different exporter use a new process (ADR-2).

**Processors only do what OpenTelemetry allows.**
- `RunContextProcessor.on_start` gets a *mutable* span. It sets run-level attributes on **every** span, including every model-call span:
  - `harness.run_id`, `harness.suite_id`;
  - `harness.prompt.sha256`, `harness.system_prompt.sha256`;
  - `harness.model.id`, `harness.model.params`;
  - `harness.span_kind` (agent, cycle, model, tool or harness), derived from the span name (ADR-2).
- `ArchiveProcessor.on_end` gets a read-only span and **serializes it to a dict immediately**, before any later processor runs, then buffers the dict. Uploads (span parts and tool-result files) run on one background writer thread fed by a queue, so the agent never waits on S3. `force_flush()` blocks until the queue is empty, with a 60-second limit.

Nothing is added to a span after it has ended. Anything that depends on a result is recorded in our decision spans instead.

**Decision spans.** `HarnessHooks` is a Strands `HookProvider` using these events ([Strands hooks](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/), accessed 2026-11-03):

| Hook | Emits (a span that ends immediately) | Attributes |
| --- | --- | --- |
| before the agent starts (`BeforeInvocationEvent`) | `harness.run.start` | `harness.tools.available` (JSON `[{server, tool, input_schema}]` from `list_tools`), `harness.limits` |
| `AfterModelCallEvent` | `harness.model_result` | `harness.model.call_index`; `harness.model.input_messages_delta`, a JSON list of the messages added since the previous model call (for call 0, the system prompt reference and the user prompt), plus `harness.model.input_message_count`; `harness.model.output` (the full assistant message as JSON); `harness.reasoning.available` (bool); `harness.reasoning.text`; `harness.reasoning.kind="summarized"`; `harness.stop_reason`; `harness.usage.input_tokens`; `harness.usage.output_tokens`; `harness.model.latency_ms` (from a `BeforeModelCallEvent` timestamp) |
| `AfterToolCallEvent` | `harness.tool_result` | `harness.tool.ref` (`T1`, `T2`…); `harness.tool.use_id`; `harness.tool.server`; `harness.tool.name`; `harness.tool.arguments` (JSON); `harness.tool.result` (the first 16 KB of text); `harness.tool.result_sha256`; `harness.tool.result_uri` (the full result, below); `harness.tool.result_truncated`; `harness.tool.status`; `harness.tool.latency_ms`; `harness.tool.attempt`; `harness.tool.repeat_of` |
| after the agent ends (`AfterInvocationEvent`, or the `finally` in `main.py`) | `harness.run.end` | `harness.status`, `harness.tool_refs` (JSON `{ref: use_id}`), `harness.archive_errors` |

**The model-call record for AC2 is `harness.model_result`.** It carries every AC2 model field:
- model ID, parameters and system-prompt hash, set by `RunContextProcessor.on_start` on every span;
- input messages, as the run's deltas concatenated in `call_index` order;
- the output, reasoning and token usage.

The checker needs no Strands span content for AC2. Strands spans are kept for the CloudWatch view and the AC4 test.

**Tool timing and retries** (AC2):
- `BeforeToolCallEvent` stores a monotonic start time keyed by `tool_use_id`. `AfterToolCallEvent` computes `harness.tool.latency_ms` from it.
- **Attempt** is a re-execution of the *same* `tool_use_id`, the kind Strands' `AfterToolCallEvent.retry` triggers. It's 0 for the first execution, and the hook counts per `tool_use_id`.
- **Repeat** is the model calling the same tool again with identical arguments under a new `tool_use_id`. `harness.tool.repeat_of` holds the earlier ref.
- AC2's "retry number" is `harness.tool.attempt`. Trouble spots follow the single rule in ADR-3.
- **Concurrent tools.** Strands may run tools in parallel, so ref numbering, attempt counters and the archive's part counter are guarded by a lock. Refs are assigned in `BeforeToolCallEvent` order, **once per `tool_use_id`**. A retry of the same `tool_use_id` keeps its ref and increments `harness.tool.attempt`. Each attempt writes its own `tool_results/<ref>.a<attempt>.txt` and emits its own `harness.tool_result` span, and `tool_refs` maps each ref to exactly one `tool_use_id`. Provenance grades a ref against its **highest attempt**, the result the model actually saw last. The retry flag (`AfterToolCallEvent.retry`) is shown in the [Strands hooks](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/) examples.
- **16 KB cap.** The same `AfterToolCallEvent` hook that adds the `[ref Tn]` label also truncates what the model sees at 16 KB, appending `[truncated; full result archived as Tn]`.

**Checker pass rules for "full" content (AC2).** The spec asks for the full input messages and the full result. They're stored in two pieces, so the checker passes them only when the pieces reassemble exactly:
- **Input messages.**
  - `input_message_count(i)` is `len(agent.messages)` just before model call `i`.
  - `input_messages_delta(i)` is `agent.messages[count(i−1):count(i)]`, with `count(−1)=0`.
  - Pass if `call_index` runs 0..n−1 with no gaps, `len(delta(i)) == count(i) − count(i−1)` for every call, and no `harness.model.messages_trimmed=true`. The full input for call `i` is the concatenation of deltas 0..i.
- **Tool result.** Pass if all of these hold:
  - the file at `harness.tool.result_uri` exists;
  - its SHA-256 equals `harness.tool.result_sha256`;
  - `harness.tool.result_truncated` is true exactly when the file is longer than 16 KB.
- **Fixtures,** each reporting exactly its failure: a missing result file; a hash mismatch; a gap in `call_index`; a delta whose length doesn't match its counts; a trimmed history.

**Full tool results.** The hook writes each full tool result to `runs/<run-id>/tool_results/<ref>.txt` through the archive writer. The span carries the first 16 KB, the SHA-256 and that path. Provenance (AC6) always matches against the full file, so a value past 16 KB is graded correctly. Spans stay small enough for the backends; S2 checks that a span with a 16 KB attribute reaches CloudWatch.

How the hooks get their data:
- **Reference labels.** `AfterToolCallEvent.result` is writable, so the hook prepends `[ref Tn] ` to the tool result text before the model sees it. **Tested:** with a tool result starting `[ref T1]`, Haiku 5.5 and Sonnet 5.5 both cited `"T1"` for all three claims. With only Bedrock's `toolUseId` available, both returned `null` and said they couldn't see an ID.
- **Conversation history must not be trimmed.** Input messages are rebuilt from per-call deltas (AC2), so the agent is created with Strands' no-op conversation manager (`NullConversationManager`), never the default, which may trim history. The class name and the default behavior are **(unverified, S1)**. As a guard, `HarnessHooks` checks before each model call that `len(agent.messages)` hasn't shrunk since the last call. If it has, it sets `harness.model.messages_trimmed=true` on the `harness.model_result`, and the checker reports it as a missing-field failure for AC2.
- **Model results** (S1, confirmed): `AfterModelCallEvent.stop_response.message` holds the output. Reasoning is at `content[].reasoningContent.reasoningText.text`, tokens at `metadata.usage` and latency at `metadata.metrics.latencyMs`. `stop_response.stop_reason` gives the stop reason.
- **Tool latency** comes from `AfterToolCallEvent.duration` (seconds), and the input cap from `BeforeModelCallEvent.projected_input_tokens`. Cooperative cancel sets the `cancel` field every `Before*` event has (S1).
- **Tool arguments.** `tool_use` comes from `BeforeToolCallEvent`, which the docs show as writable `tool_use`/`selected_tool`. It's carried to the matching `AfterToolCallEvent` by `tool_use_id`.

**Agent spans** are the spans from the Strands tracer's instrumentation scope, `strands.telemetry.tracer` (S1), plus our `harness` scope. The MCP library's own `MCP send …` client spans are excluded. ADOT auto-instrumentation adds spans in other scopes, such as botocore and HTTP. The archive keeps every span with its scope name, but checks, signals, reports and AC4 count **agent spans only**. Strands' span names (S1) map to `harness.span_kind` like this: `invoke_agent*` → agent, `execute_event_loop_cycle` → cycle, `chat` → model, `execute_tool*` → tool. Message content is in span events (`gen_ai.*.message`, `gen_ai.choice`), which the archive keeps.

**Model.** `BedrockModel(model_id=payload.model_id, max_tokens=payload.model_params.max_tokens, additional_request_fields=payload.model_params.request_fields)`. The params come from the model's entry in `harness.yaml`, are sent in the payload, and are recorded verbatim as `harness.model.params`. So AC2 records the real values, and a model that rejects thinking fields just gets an entry without them (AC10). Client config: botocore `Config(connect_timeout=10, read_timeout=120, retries={"mode":"standard","max_attempts":3})`. Whether `BedrockModel` accepts a client config is **(unverified, S1)**.

**Tested:**
- Every sandbox `converse` call that returned reasoning used `output_config: {effort: high}` together with `thinking: {type: adaptive}`. Bedrock rejected `thinking.type=enabled`, and its error message named `thinking.type.adaptive` and `output_config.effort` as the supported controls.
- In the sandbox, Claude is available only through inference profiles, e.g. `us.anthropic.claude-haiku-5-5` and `us.anthropic.claude-sonnet-5-5` (`aws bedrock list-inference-profiles`).
- `thinking.type=enabled` is rejected.
- `adaptive` with `display: summarized` returns about 1,200 characters of summarized reasoning on Haiku 5.5. Without `display`, the block comes back empty, with only a signature.
- Sonnet 5.5 skipped thinking on a trivial question, so `harness.reasoning.available=false` is a normal value, not an error.

**Tools.**
- RODA: `MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["--offline", "awslabs.roda-mcp-server@0.1.7"])))`, with the uv cache pre-warmed at image build (`uvx awslabs.roda-mcp-server@0.1.7 --help`), so a cold start doesn't depend on PyPI. If `--offline` fails, it retries once online. The `--offline` flag and the pre-warm command are **(unverified, S2)**; the fallback is the online `uvx` call alone. This follows the documented stdio pattern ([Strands MCP tools](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/mcp-tools/), accessed 2026-11-03). Pinned to 0.1.7, whose tools include `search_datasets`, `get_dataset_details` and `preview_dataset`; preview needs no AWS account ([PyPI 0.1.7](https://pypi.org/project/awslabs.roda-mcp-server/)). `uv` is baked into the image.
- LGND Geo: remote HTTP MCP at `https://geo.lgnd.ai/mcp`, covering NAIP below 1 m for the contiguous US from 2020 to 2023 ([lgnd.ai/resources/lgnd-geo](https://lgnd.ai/resources/lgnd-geo), accessed 2026-11-03). Headless auth is **(unverified, S3)**. Until it works, the agent starts with RODA only and records LGND as unavailable in `harness.run.start`.

**Limits.** These are set in `harness.limits` and enforced by `HarnessHooks`:
- **Steps:** at most 40 model calls plus tool calls. The 41st `BeforeModelCallEvent` or `BeforeToolCallEvent` raises `LimitExceeded`. Raising from a hook propagates, per the hooks docs.
- **Output tokens:** `max_tokens` is 16,000 per call, because thinking tokens count against it. At most 200,000 output tokens per run, checked like input tokens: *used + max_tokens > 200,000* stops the run. A model result with `stop_reason=max_tokens` is a trouble spot. If it's the final answer, the run ends `error` with `error: "final answer truncated at max_tokens"`, and AC6 reports the missing or partial claims block.
- **Input tokens:** at most 400,000 input tokens per run, summed from `harness.usage.input_tokens`. At every `BeforeModelCallEvent`, the check is *used so far + the previous call's input tokens* (the next call's context is at least that large) > 400,000, so the last call can't overshoot by a whole context.
- **Tool calls:** a 60-second timeout per tool call. S1 found that `MCPClient` has only `startup_timeout`, and that `MCPAgentTool` calls `call_tool_async` without `read_timeout_seconds`. So `agent/tools.py` wraps each MCP tool in a thin `AgentTool` that calls `call_tool_async(..., read_timeout_seconds=timedelta(seconds=60))`.
- **Wall clock:** `main.py` runs the agent in a worker thread and waits 600 seconds. Python can't kill a thread, so cancellation is cooperative:
  - On timeout, `main.py` sets a `cancel` flag that `HarnessHooks` checks at every `Before*` event. The next model or tool call raises `LimitExceeded`, so no new paid call starts.
  - `main.py` waits up to 180 more seconds for the thread to stop: the longest in-flight call is a 120-second model read.
  - It then emits `harness.run.end` either way.
  - If the thread is still running, it's abandoned. Spans it emits after `harness.run.end` get `harness.after_end=true`, and analysis ignores them.
  - The worst-case invocation is 600 + 180 = 780 seconds, inside the CLI's 900-second read timeout.

**End of every invocation.** `main.py`'s `finally` does four things, in order:
1. emits `harness.run.end`;
2. calls `ArchiveProcessor.force_flush()`, which writes the current buffer as the next `spans-NNNN.jsonl` part and waits for it;
3. writes `result.json`;
4. returns the response.

So the archive is complete before the CLI reads it, even though the session process outlives the invocation.

**Run context.** It's held in module-level state in `agent/main.py`, set at the start of each invocation and read by `RunContextProcessor` and `HarnessHooks`. That state is visible from Strands' tool threads; a `contextvars` value wouldn't be. Each run uses its own session ID (the run ID), and the CLI never sends two invocations to one session at once.


**Invocation.** The CLI calls the `bedrock-agentcore` client's `invoke_agent_runtime(agentRuntimeArn, runtimeSessionId=<run-id>, payload)` ([observability guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)) with these settings:
- botocore `Config(read_timeout=900, connect_timeout=10, retries={"max_attempts":1})`, so a slow run is never resent automatically.
- The CLI itself retries only `RetryableConflictException`. The docs describe that error as a session still being provisioned: "transient and retryable", with short exponential backoff ([HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)). It retries 3 times, after 1, 2 and 4 seconds. That error means the agent hasn't started, so retrying can't double-run it.

The maximum duration of a synchronous invocation isn't stated in the contract **(unverified, S2)**. If S2 shows that a 10-minute synchronous call fails, the agent switches to the documented background pattern: it returns `{"status":"accepted"}` straight away, reports `HealthyBusy` on `/ping` while it works (same contract page), and writes `result.json`. The CLI then checks for `result.json` every 10 seconds, for up to 15 minutes.

## Data and contracts

Every file carries `schema_version: 1`. Old runs stay readable because the archive holds raw spans; changing these contracts later is costly, but not a one-way door.

**Archive URI.** `archive_uri` in `harness.yaml` and `HARNESS_ARCHIVE_URI` in the runtime: `s3://<bucket>` in AWS, or `file://./archive` for local development and tests. `archive.py` and `analysis/trace.py` both accept either scheme.

**Layout.**

| Path | Written by | When |
| --- | --- | --- |
| `runs/<run-id>/spans-0001.jsonl`, `spans-0002.jsonl`, … | agent `ArchiveProcessor` | every 50 spans and at shutdown |
| `runs/<run-id>/tool_results/<ref>.a<attempt>.txt` | agent `HarnessHooks` | after each tool execution (the full, raw result text) |
| `runs/<run-id>/result.json` | agent `main.py` | at the end, in a `finally`, after `force_flush` (same fields as the invocation response) |
| `runs/<run-id>/run.json` | CLI | at the start (`status: running` plus snapshots) and at the end (merged with `result.json` or the invocation response) |
| `runs/<run-id>/summary.json` | CLI | after the run (the narrative, ADR-3) |
| `suites/<suite-id>/suite.json` | CLI | at the start; updated after each run (`{suite_id, suite_file_sha256, run_ids: [...]}`) |

- **Suite ID:** `<suite name>-<UTC yyyymmddThhmm>`. `compare` reads only `suite.json` and the listed runs, so it never scans the bucket.
- **A failed run doesn't stop its suite.** The run is still listed in `suite.json`. The CLI ends with `suite … done: 3/4 runs ok, 1 failed (run 77de…: <reason>)`, and `compare` shows the failed row with its status and reason; its signals cover the spans that were archived.
- **S3 reads and writes** (agent and CLI): botocore `Config(connect_timeout=5, read_timeout=30, retries={"mode":"standard","max_attempts":3})`.
- **Archive write failures:** a failed write is counted in `harness.archive_errors` and returned in the invocation response, and the CLI records it in `run.json`. The CLI's own S3 access is separate from the agent's.

**Invocation contract** (`harness/invoke.py` ↔ `agent/main.py`, JSON):
```json
// request payload
{"schema_version":1,"run_id":"<uuid4>","suite_id":null,"prompt":"<prompt text>","prompt_file":"prompts/dallas-dc.md",
 "prompt_sha256":"…","model_id":"us.anthropic.claude-haiku-5-5","model_params":{"max_tokens":16000,"request_fields":{"thinking":{"type":"adaptive","display":"summarized"},"output_config":{"effort":"high"}}},
 "limits":{"max_steps":40,"max_input_tokens":400000,"wall_clock_s":600,"tool_timeout_s":60}}
// response
{"schema_version":1,"run_id":"…","status":"ok|error|limit_exceeded","error":null,"final_output":"…",
 "tool_refs":{"T1":"<tool_use_id>"},"archive_errors":0}
```
`run_id` is also the `runtimeSessionId`. The model ID travels in the payload, so a model swap (AC10) needs no redeploy. A payload with an unknown `schema_version` or missing fields is rejected with `status: error` and `error: "bad payload: <field>"`.

**Span line** (serialized in `on_end`):
```json
{"schema_version":1,"scope":"<instrumentation scope name>","trace_id":"…","span_id":"…","parent_span_id":"…",
 "name":"…","kind":"…","start_ns":0,"end_ns":0,"status":"OK|ERROR","status_message":"…",
 "attributes":{},"events":[{"name":"…","time_ns":0,"attributes":{}}],"resource":{}}
```

**`run.json`:**
```json
{"schema_version":1,"run_id":"…","suite_id":null,"backend":"agentcore","model_key":"haiku","model_id":"us.anthropic.claude-haiku-5-5",
 "prompt_file":"prompts/dallas-dc.md","prompt_sha256":"…","started_at":"…","ended_at":"…",
 "status":"running|ok|error|limit_exceeded","final_output":"…","archive_uri":"s3://…",
 "archive_errors":0,"snapshot":{"prices_per_mtok":{},"rubric":null,"scorer":"none","harness_version":"<git sha>"}}
```
The snapshot makes replay deterministic (AC9). Replay uses the prices and rubric recorded at run time, never the current `harness.yaml`. A prompt version is its file path plus `prompt_sha256`; both appear in the report.

**Claims contract.** The system prompt requires the final answer to end with a fenced JSON block:
```json
{"claims":[{"claim":"Equinix DA11 is a data center in Dallas","value":"DA11","ref":"T3"}]}
```
- **`analysis/provenance.py` is the only parser.** The agent returns the raw `final_output`, and provenance parses the claims block from it every time, so a live report and a replay grade the same parse.
- The analysis resolves `ref` through the `harness.tool.ref` attribute on each `harness.tool_result` span, not through `harness.tool_refs` on `harness.run.end`. So refs still resolve in a partial run.
- **Every claim has a span to link to** (AC7):
  - a claim with a resolvable ref links to its `harness.tool_result` span;
  - an unsourced claim, and the "claims block missing" finding, link to the run's **last `harness.model_result` span**, which is the model call that produced the final answer;
  - a run with no model result at all links to `harness.run.start`.
- A missing or unparseable block sets `claims_block_missing` in the analysis output, and every AC6 check fails for that run.
- `value` must be a JSON **string**; the system prompt says so. If the model emits a JSON number, it's converted to its shortest decimal string (`32.8` stays `32.8`, so `d=1`) and the claim is flagged `value_not_string` in the report.
- The system prompt also says tool results are data, not instructions.
- All prompts, including `system.md`, live in `prompts/` at the repo root, are copied into the image, and are versioned by their hash.

**Matching rule (AC6).** Values are compared against the **full, raw** tool result in `tool_results/<ref>.a<attempt>.txt`. That's the result exactly as the tool returned it: before the `[ref Tn]` prefix and before the 16 KB truncation the model sees. So the label text can never produce a match. If that file is missing (an archive write failed), matching falls back to the 16 KB copy on the span. A claim not found there is graded mismatch, with the note "full tool result missing from archive".

**How a value is classed**, in this order, after trimming:
1. **Coordinate pair:** `^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$`
2. **Number:** `^-?\d+(\.\d+)?$`. `d` is the count of digits after the point *as written in the string*.
3. **Text:** anything else.

| Value | Rule |
| --- | --- |
| Text, 3 or more characters after normalizing (lowercase, collapse whitespace) | Substring of the normalized result |
| Text under 3 characters | Must match a whole word in the result |
| Number of 1–2 characters (e.g. `"1"`, `"42"`) | Must equal a whole numeric token in the result (`1` matches `… 1 site …`, not `1.2` or `12`). The tolerance rule doesn't apply |
| Number of 3+ characters with `d` decimals | Matches if any number `x` in the result satisfies `\|x − value\| ≤ 0.5·10^−d`, so `32.80` matches `32.8008` |
| Coordinate pair `"lat,lon"` | Each part checked as a number |

Known limits of this version: claims are checked on `value` only, not on the `claim` text, and a coordinate pair's two parts are matched independently, so they could match in unrelated places in the result.

**Datasets accessed (AC2).** `analysis/datasets.py` maps each tool to the argument or result field that names a dataset. RODA (S1): the `slug` argument of `get_dataset_details`, `preview_dataset`, `sample_dataset` and `find_related_datasets`, plus each `results[].slug` in a `search_datasets` or `list_datasets` result. LGND tools give the imagery source (Sentinel-2 or NAIP); those field names come from S3. A tool with no mapping is listed as "dataset unknown", never silently dropped.

**Suite file** (`suites/*.yaml`, read by `harness run --suite`):
```yaml
suite: dallas-dc-v1                 # name; the suite ID is <name>-<UTC yyyymmddThhmm>
prompts: [prompts/dallas-dc.md, prompts/dallas-dc-strict.md]   # paths relative to the repo root
models: [haiku, sonnet]             # keys into harness.yaml models
backend: agentcore                  # optional; defaults to harness.yaml backend
```
Runs execute in prompt-major order (every model for prompt 1, then prompt 2). An unknown model key or a missing prompt file is rejected before anything runs: `suite dallas-dc-v1: unknown model key 'opus' (known: haiku, sonnet).`

**Rubric file** (`rubrics/*.yaml`, optional; configured as `rubric:` in `harness.yaml`):
```yaml
rubric: adb-dallas-dc
version: 1
criteria:
  - {id: completeness, question: "Are all data centers in the answer key found?", scale: "0-5"}
```
`analysis/score.py` defines a `Scorer` interface, `score(run, rubric) -> [{criterion_id, score|null, rationale}]`. This version ships only the `none` scorer, which returns `null` for every criterion, so the report lists the criteria as "not scored". Which scorer to use is still open, per the spec.

**`harness.yaml`** (committed, no secrets):
```yaml
region: us-west-2
archive_uri: s3://<from CDK output>
runtime_arn: <from CDK output>
backend: agentcore            # agentcore | local; --backend overrides it per run
local_exporter: console       # HARNESS_EXPORTER for --backend local: console | otlp
local_archive_uri: file://./archive
models:
  haiku:
    id: us.anthropic.claude-haiku-5-5
    max_tokens: 16000
    request_fields: {thinking: {type: adaptive, display: summarized}, output_config: {effort: high}}
  sonnet:
    id: us.anthropic.claude-sonnet-5-5
    max_tokens: 16000
    request_fields: {thinking: {type: adaptive, display: summarized}, output_config: {effort: high}}
narrative_model: haiku
max_runs_per_suite: 8
max_suite_usd: 50
prices_per_mtok: {haiku: {in: <usd>, out: <usd>}, sonnet: {in: <usd>, out: <usd>}}  # from the Bedrock pricing page; URL in a comment
rubric: null
scorer: none
```

## Decisions

### ADR-1: Where telemetry goes
- **Context:** The team dropped Phoenix and the live two-backend demo **[team]**. One deployed runtime uses AgentCore Observability (CloudWatch). The exporter must still be pluggable by config (AC3, AC4), and ADOT is configured when the process starts.
- **Options:**
  - A) One runtime with ADOT → CloudWatch. Outside the runtime, the exporter is chosen by `HARNESS_EXPORTER`.
  - B) Two runtimes, one per backend. This was the earlier design, dropped with Phoenix.
  - C) An OpenTelemetry Collector in front of every backend.
- **Decision:** A.
- **`HARNESS_EXPORTER` values:**
  - `adot`: the deployed runtime.
  - `otlp`: any OTLP/HTTP backend, configured with the standard `OTEL_EXPORTER_OTLP_*` variables ([Strands traces](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/)).
  - `console`: local runs and tests.
- **Why:** It's the least infrastructure: no second runtime, no Phoenix hosting. Adding a backend later means setting `HARNESS_EXPORTER=otlp` and an endpoint, with no code change.
- **Reversibility:** easy.
- **Sources:** `AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT=true` "keeps model payloads and tool request/response data on spans" ([observability guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html), accessed 2026-11-03). It's documented for agents outside the runtime; whether it applies inside is **unverified, S2**. Either way the archive has full content, because our decision spans carry it.

**Where the agent runs** (`harness.yaml` `backend`, with `--backend` overriding it per run):
- `agentcore`: the CLI invokes the deployed runtime.
- `local`: the CLI runs `python -m agent.local <payload.json>` in a subprocess. `agent/local.py` calls the same `handle(payload) -> response` function that `agent/main.py`'s `/invocations` route calls, so only the HTTP layer is skipped. It uses `HARNESS_EXPORTER` from `local_exporter` (default `console`) and `HARNESS_ARCHIVE_URI=local_archive_uri` (default `file://./archive`). The CLI reads the response from `result.json` in the local archive, never from the subprocess's stdout. The exit code only signals crash (non-zero) or completion (0).

**Finding a run's archive.** Each run's `run.json` records its `archive_uri`, and the CLI keeps a local index, `out/index.json`, mapping each run and suite ID to its archive URI. `check`, `replay` and `compare` look up the index first and fall back to `archive_uri` from `harness.yaml`. Both lookups are single-key reads, never scans. Local and deployed runs have the same archive layout and give the same reports.

| Runtime variable (`agent-agentcore`) | Value |
| --- | --- |
| `HARNESS_EXPORTER` | `adot` |
| ADOT | runtime defaults, plus `AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT=true` |
| `HARNESS_ARCHIVE_URI` | `s3://<bucket>` |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `gen_ai_latest_experimental,gen_ai_tool_definitions` ([Strands traces](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/)) |
| `OTEL_TRACES_SAMPLER` | `always_on`. It ignores any parent or incoming sampling decision, so no span is dropped before the archive sees it. It's a standard variable that the Strands traces page shows; whether ADOT honors it over its own default is **(unverified, S2)**. Local and test providers are built with an always-on sampler in code |

### ADR-2: How pluggability is proven (AC4)
- **Context:** Without a live second backend, AC4 is a CI test: the same agent activity goes through two exporters, with only config changed.
- **Options:**
  - A) Run a deterministic agent in **two separate subprocesses** through the real `telemetry.py`: once with `HARNESS_EXPORTER=otlp` sending to an OTLP/HTTP receiver run by the test, and once with `HARNESS_EXPORTER=console` and `HARNESS_CONSOLE_PATH=<tmp file>`.
  - B) Replay recorded spans through two exporters.
  - C) Unit-test each exporter on its own.
- **Decision:** A.
- **How:**
  - Each case is `python -m agent.local <payload.json>` with `HARNESS_TEST_SCRIPT=tests/fixtures/scripted_run.json`. That switches only the external boundaries: a scripted model provider in place of Bedrock (a fixed tool call, then a fixed final answer with a claims block), and a local function in place of the MCP tool. Everything else is the real code path: `telemetry.py`, the processors, the hooks and the archive (`file://`).
  - Separate processes mean each case gets a fresh, explicitly passed provider. Nothing can leak between them through OpenTelemetry's set-once global provider.
  - The test receiver is a small HTTP server on localhost, run by the test, that decodes OTLP protobuf (`opentelemetry-proto`). The console case is read back from the tmp file.
  - The test asserts that both exporters received the same agent spans by count and by `harness.span_kind`, which `RunContextProcessor` sets in `on_start` from the Strands span name. It also asserts that the same code ran in both cases: the same `telemetry.py`, with no flags beyond the environment.
- **Why:** It exercises the real wiring, from `boot.sh` choices to `telemetry.py`, the processors and the exporter. B wouldn't exercise Strands' instrumentation; C wouldn't prove the swap.
- **Risk:** whether Strands accepts a custom, scripted model provider is **(unverified, S1)**. Fallback: B, using spans recorded from a real local run.
- **AC3, the import-lint rule** (deterministic). The test does two things:
  1. It parses every `.py` file under `agent/`, `harness/` and `analysis/` with `ast`. It fails if any import's top-level module is neither the standard library (`sys.stdlib_module_names`) nor a first-party package nor a dependency declared in `pyproject.toml`.
  2. It fails if any declared dependency is missing from `tests/allowed_deps.txt`, a reviewed allowlist. That list contains `opentelemetry-*`, `strands-agents`, `bedrock-agentcore`, `boto3`, `jinja2`, `pyyaml`, `mcp` and no observability-backend SDK.

  Adding a backend SDK therefore means a visible edit to the allowlist in review.
- **Reversibility:** easy.

### ADR-3: Narrative summary
- **Context:** AC7 needs an exact trouble-spot list, and AC9 replay can't call a model.
- **Options:**
  - A) Code only.
  - B) LLM only.
  - C) A code-generated structure plus an LLM narrative.
- **Decision:** C.
- **How:**
  - `summary.py` builds the ordered steps, ordered by span start time with the span ID breaking ties, and the trouble spots. **Trouble-spot rule** (the only definition; the AC7 fixture is built against it). A trouble spot is any of:
    - an agent span with ERROR status;
    - a `harness.tool_result` with `harness.tool.status=error`;
    - a `harness.tool_result` with `harness.tool.attempt > 0`;
    - a `harness.tool_result` with `harness.tool.repeat_of` set;
    - a claim graded mismatch or unsourced;
    - the run ending `limit_exceeded`, attached to the `harness.run.end` span.
  - The CLI then makes one narrative call to `narrative_model`, giving it only that structure (60-second read timeout, 1 retry after 2 seconds), and saves the result to `summary.json`.
  - Span IDs in the narrative that aren't in the trace are removed before saving, and that is logged.
- **Reversibility:** easy.

### ADR-4: Infrastructure as code
- **Decision:** CDK in Python. The `aws_bedrockagentcore` module exists in aws-cdk-lib ([CDK API](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/RuntimeNetworkConfiguration.html)). The construct that creates a runtime, and how it takes the image and environment variables, is **(unverified, checked at the start of slice 3)**.
- **Fallback:** the `bedrock-agentcore` starter toolkit, scripted in `infra/deploy.sh`.
- **Image:** built as `linux/arm64`, as the HTTP protocol contract requires.
- **Tags:** every resource gets `Project=team46-eval-harness`, `Owner=team46` and `CostCenter=hackathon-sandbox` through `Tags.of(app)`.
- **Reversibility:** easy.

## Failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Bedrock throttling or error | model call raises after 3 botocore attempts | Run ends `error`; the decision spans so far are archived | Report shows the failed step; rerun |
| Bedrock call hangs | 120 s read timeout | Same as above | Same |
| RODA subprocess fails to start | `MCPClient` error at start | Run fails fast: `tool server roda unavailable` | Image includes `uv`; fallback in S2 |
| LGND auth fails or times out | 60 s tool timeout or an auth error | Agent continues with RODA; `harness.tool_result` records the error as a trouble spot | Fix credentials; rerun |
| Model loops | step counter in hooks | `LimitExceeded` at 40 steps, status `limit_exceeded` | Report shows where it looped |
| Run exceeds 10 minutes | `main.py` wait | Status `limit_exceeded`; `harness.run.end` emitted | Same |
| Runtime crashes mid-run | CLI gets an invocation error, or no `result.json` | Up to 50 spans lost. The Strands root span may be missing, so analysis anchors on `harness.run.start` (which ended at the start, so it's archived) and shows the "Run ended early" banner | `harness replay` shows the partial run |
| Invocation exceeds the sync limit | `ReadTimeout` or a service error | The CLI doesn't retry; `run.json` gets `status: error` with the reason | Background pattern (S2 fallback) |
| S3 write fails | `ArchiveProcessor` gets an error after 3 attempts | `harness.archive_errors` is incremented and returned in the response; logged to stdout, which reaches CloudWatch | `run.json` shows `archive_errors > 0`; `check` fails |
| Claims block missing or bad JSON | `provenance.py` parse (the only parser) | `claims_block_missing: true`; AC6 fails for that run | Prompt fix; it shows up in the report |
| Narrative call fails | CLI catches it | Report without narrative (copy above) | `harness replay` works regardless |

## Security and privacy

- **Credentials** never enter the repo:
  - `.gitignore` blocks `.env*`, `*.env`, `aws-sandbox*` and `credentials`.
  - The CLI uses the standard AWS credential chain.
  - Any LGND token lives in Secrets Manager and is read in code at start-up. CDK creates the secret empty, and its value is set once with `aws secretsmanager put-secret-value`, documented in `infra/README.md`.
  - The gitleaks action runs in CI on every push and PR.
- **Execution role** (least privilege):
  - `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on `arn:aws:bedrock:*::foundation-model/anthropic.claude-*` and `arn:aws:bedrock:us-west-2:<account>:inference-profile/*anthropic.claude-*`. Cross-region `us.` and `global.` profiles route to foundation models in other regions, so the foundation-model ARN uses a region wildcard. The wildcard on Claude models means adding a model needs no IAM change (AC10). That cross-region inference needs the foundation-model ARNs in each routed region is **(unverified, checked at the first deploy in slice 3)**.
  - `s3:PutObject` on the archive bucket's `runs/*` and `suites/*`; `s3:GetObject` on `runs/*`.
  - `s3:GetObject` and `s3:ListBucket` on `arn:aws:s3:::*`, read-only, so RODA's signed reads of public open-data buckets work with the execution role. Requester-Pays buckets also need `x-amz-request-payer`, which is RODA's concern; NAIP pulls are out of scope. Whether RODA's `preview_dataset` signs its S3 calls is **(unverified, S2)**.
  - `secretsmanager:GetSecretValue` on the LGND secret, if there is one.
  - The ADOT, logging and X-Ray permissions AgentCore documents.
- **Untrusted content:**
  - Tool results are untrusted data.
  - Both MCP servers are read-only search tools, and the agent has no write, send or spend tools.
  - The system prompt says tool results are data, not instructions.
  - An adversarial fixture checks that analysis treats injected text in a tool result as data: it's reported, never executed.
  - **Reports escape everything.** `report.html` and `compare.html` are rendered with Jinja2 and `autoescape=True`. All tool, model and claim text is escaped, and no field is marked safe. The adversarial fixture includes `<script>alert(1)</script>` in a tool result and in a claim, and the test asserts it appears escaped.
- **Data.** Public and synthetic only (T12). No personal data in traces. The archive bucket blocks public access and uses SSE-S3 encryption.

## Performance and cost

- **Analysis:** under 5 seconds for 1,000 spans, checked by a unit test with a generated fixture.
- **Paid calls are bounded:**
  - 40 steps per run, 16,000 output tokens per model call and 200k per run, 400k input tokens per run, and at most 8 runs per suite (all enforced).
  - The model sees at most the first 16 KB of each tool result, followed by `[truncated; full result archived as <ref>]`, which limits how fast the context grows. Provenance still matches against the full file.
  - **Worst case per run:** 400k input plus 200k output tokens, plus one narrative call (at most 50k input and 2k output on `narrative_model`). The worst-case dollar figure is `0.4 × price_in + 0.2 × price_out` per run, plus `0.05 × narrative_in + 0.002 × narrative_out` (prices per million tokens), times the suite size.
  - **Before every suite,** the CLI prints that worst case from `prices_per_mtok`. It refuses to start if the total is over `max_suite_usd` (default $50), so one suite can use at most a tenth of the $500 cap. A single `harness run` prints its worst case too. Any command that invokes a model refuses to run while `prices_per_mtok` still holds placeholders: `prices_per_mtok.haiku is not set; fill it from the Bedrock pricing page.` The prices come from the Bedrock pricing page at setup, because they aren't verified here.
- **Budget:** CDK creates an AWS Budgets alert at $100 actual and $250 forecast, emailed to the address in CDK context `budget_email`. It's passed at deploy time (`cdk deploy -c budget_email=…`) and never committed. If the participant role can't create budgets, which is **unverified**, the fallback is a daily manual Cost Explorer check, noted in `infra/README.md`.

## Migration and rollback

The repo is greenfield, so nothing is migrated. Rollback is `cdk destroy`, which removes the runtime, the role and the budget. The archive bucket is retained (`RemovalPolicy.RETAIN`) so recorded runs survive for replay. **One-way door:** deleting the bucket destroys recorded runs. It's a separate manual step, only after judging, and needs explicit confirmation.

**One-time account setup**, before the AgentCore backend shows spans:
- Enable CloudWatch Transaction Search. The sandbox currently reports `Destination: XRay` (tested with `aws xray get-trace-segment-destination`).
- It's done with `aws xray update-trace-segment-destination --destination CloudWatchLogs`, plus a logs resource policy for `xray.amazonaws.com` ([observability guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)).
- To undo it after the event: `aws xray update-trace-segment-destination --destination XRay`, which restores the state recorded today, and `aws logs delete-resource-policy` for the policy we added.
- It's account-wide, so it's run only after the human confirms.

## Traceability

| AC | Component(s) | Test(s) |
| --- | --- | --- |
| AC1 Run | `harness/invoke.py`, `agent/main.py`, `infra/` | Live smoke (`tests/live/smoke.sh`): `harness run --prompt prompts/dallas-dc.md` exits 0 and `run.json` has status `ok` |
| AC2 Decisions traced | `RunContextProcessor`, `HarnessHooks`, `analysis/check.py`, `analysis/datasets.py` | Unit: the checker on a complete fixture reports 0 missing. On fixtures with each required field removed (a `model_result` without the system-prompt hash or input messages; a `model_result` with neither reasoning text nor `available=false`; a `tool_result` without arguments, latency or attempt) it reports exactly that field. Live: `harness check` on the smoke run |
| AC3 OTel only | `agent/telemetry.py` | CI: the import-lint test fails on any telemetry import outside `opentelemetry*` |
| AC4 Exporter swap | ADR-1, ADR-2, `agent/telemetry.py` | CI (`tests/test_exporter_swap.py`): the deterministic agent runs twice through the real `telemetry.py`, with `HARNESS_EXPORTER=otlp` to an in-process OTLP receiver, then `console` to a tmp file, each in its own subprocess. It asserts the same agent-span count and kinds, and that only the environment differed. Localhost is the only network allowed. Live sanity check: after the smoke run, the agent's spans are visible in CloudWatch (`/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>` stream `spans`, or `aws/spans`, per the [observability guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)) |
| AC5 Archive | `agent/archive.py` | Unit: with `file://` and with moto-faked S3, it writes the expected JSONL, flushes at 50 spans and on `force_flush()`, and serializes in `on_end` (a later processor that mutates attributes doesn't change the archived line) |
| AC6 Provenance | `HarnessHooks` (refs), `analysis/provenance.py` | Unit fixtures: matched; mismatch; unsourced (no ref, and a ref to a non-tool span); a missing block; a coincidental short value ("1"); a rounded coordinate (`32.80` vs `32.8008`, matched) |
| AC7 Summary | `analysis/summary.py`, ADR-3 | Unit: a fixture with known trouble spots names all of them, with no unknown span IDs; the narrative filter drops an invented span ID |
| AC8 Report | `analysis/report.py`, `signals.py`, `score.py` | Unit: the fixture report has every required section and signal (including tools available, datasets accessed, cost and runtime). "awaiting rubric" appears without a rubric; a 2-criterion rubric shows both as "not scored" |
| AC9 Replay | `harness replay`, `analysis/*`, `run.json` snapshot | Unit: the report equals the replayed report, excluding the timestamp, with networking blocked (`pytest-socket`) and with prices changed in `harness.yaml` after the run |
| AC10 Model swap | `harness.yaml` models, payload, IAM wildcard | Live: a 1-prompt × 2-model suite; the archive shows two model IDs; `git diff` shows no change |
| AC11 Suite and compare | `harness run --suite`, `suite.json`, `analysis/compare.py` | Unit: 4 fixture runs and a manifest give 4 rows with every column. The CLI refuses a 12-run suite. Live: the 2 × 2 suite |

Unit tests fake only the external boundaries: S3 via moto or `file://`, and the network blocked. They run `harness` through its real entry point in a subprocess, with real config loading. No test uses sleeps; tests wait on conditions, never on time.

## Risks and spikes

Ordered by risk. Local spikes S1 and S6 run Tuesday 1:00–3:00 pm. S2 runs as the first step of slice 3, **before** slice 3 builds on it, and on a hello-world image deployed by hand-run CDK. If S2 fails, only `telemetry.py`'s provider setup and `invoke.py`'s invocation mode change; slices 1 and 2 don't depend on either. S3 runs whenever LGND access arrives.

| Spike | Question | Pass | If it fails |
| --- | --- | --- | --- |
| **S1** (local) **done, see [spikes.md](spikes.md)** | What does `AfterModelCallEvent` expose? Does `BedrockModel` pass the thinking fields through and accept a client config? What's the MCP timeout parameter? What's Strands' instrumentation scope name? What do RODA's tool schemas look like? Does Strands accept a custom (scripted) model provider for the AC4 test? What's the no-op conversation manager called, and does the default trim history? | A local run emits `harness.model_result` with reasoning text, and `harness.tool_result` with arguments and result | Read reasoning from `agent.messages`; call Bedrock through a custom model provider; enforce the tool timeout with a wrapper around `call_tool` |
| **S2** (deployed) | Does ADOT's provider accept `add_span_processor`? Can `uvx` start inside the runtime with internet access? Does a 13-minute synchronous invocation work? Does the content opt-out apply inside the runtime? Does a span with a 16 KB attribute reach CloudWatch? | A hello-world agent lists RODA tools, makes one real `preview_dataset` call that succeeds, archives 100% of spans (the decision spans the hooks emit equal the decision spans archived), and holds a 13-minute synchronous call | Our own provider plus ADOT's exporter; RODA hosted separately; the background invocation pattern |
| **S3** | Can a headless agent authenticate to LGND Geo? | `list_tools` from a script | Ask LGND or Clay for a hackathon token (spec A4); RODA only meanwhile |
| **S6** | (Informs the prompt's bound only; no scorer uses the answer key in this version.) How many OSM data centers are within 50 km of Dallas (the spec's answer key)? | An Overpass count of at least 10 | Also include `building=data_center`, or change the bound. Both Overpass mirrors failed or returned nothing on 2026-11-03 |

Phoenix was dropped, and its spikes (S4, S5) with it.

## Out of scope for this version

- An evaluation set beyond the draft prompt and one variant. Adversarial cases are covered only as analysis fixtures (AC6, Security).
- Checking the `claim` text, not just the `value`.
- Re-scoring an old run with a new rubric.

## Implementation plan

Slices are ordered riskiest first. Each ends green (tests, lint and type checks pass), runnable, and committed to `design/eval-harness`. **Toolchain:** Python 3.12 managed by `uv` (`uv python install 3.12`); `uv` 0.13.6 pinned in `.tool-versions`; podman for the arm64 image; Node for CDK.

**Slice 0: Spike S1, local and throwaway.** Code goes in `spikes/s1/` and is deleted or kept only as notes.
1. `spikes/s1/run.py`: a Strands `Agent` with `BedrockModel(us.anthropic.claude-haiku-5-5, thinking adaptive/summarized)`, RODA over stdio, a `ConsoleSpanExporter` writing to a file, and a probe `HookProvider` that logs every event's fields.
2. Run it once against the sandbox and record the answers to S1 in `docs/eval-harness/spikes.md`:
   - the scope name;
   - the `AfterModelCallEvent` fields;
   - whether `client_config` works and what the MCP timeout parameter is called;
   - the RODA schemas;
   - whether a scripted model provider works;
   - the conversation manager.
3. Update the design wherever an answer differs. **Commit:** "Spike S1 findings".

**Slice 1: Contracts and analysis on fixtures** (no AWS).
1. `pyproject.toml` (packages `agent`, `harness`, `analysis`; dev dependencies pytest, moto, pytest-socket, ruff, mypy), `.tool-versions`, `tests/allowed_deps.txt`.
2. `analysis/trace.py`: load an archive (`file://` or `s3://`), the span model, the agent-span filter (scope from S1), `harness.span_kind`.
3. `tests/fixtures/`: a builder that writes synthetic archives (spans, tool-result files, `run.json`, `suite.json`), plus the named fixtures from Traceability.
4. Test-first, one commit each:
   - `analysis/check.py` (AC2 rules);
   - `analysis/provenance.py` (AC6 parsing, classing and matching);
   - `analysis/signals.py` and `analysis/datasets.py`;
   - `analysis/summary.py` (trouble-spot rule; the narrative filter);
   - `analysis/score.py` (rubric and the `none` scorer);
   - `analysis/report.py` (Jinja2 with autoescape);
   - `analysis/compare.py`.
5. `harness/cli.py`, `config.py`, `manifest.py` (`out/index.json`): the `check`, `replay` and `compare` commands, end to end against fixtures in a subprocess. AC9 runs with networking blocked.
6. CI: `.github/workflows/ci.yml` running ruff, mypy, pytest, the import lint (AC3), and the gitleaks action. **Commit** after each numbered item.

**Slice 2: Agent, local.**
1. `agent/telemetry.py` (the `adot`, `otlp` and `console` exporters, one provider per process), `agent/archive.py` (serialize in `on_end`, background writer, `force_flush`), `agent/hooks.py` (refs, decision spans, limits, cancel, trim guard), `agent/main.py` (`handle()`, the HTTP `/invocations` and `/ping` routes), `agent/local.py`, and `prompts/system.md` plus `prompts/dallas-dc.md`.
2. Unit tests for the archive and hooks; the scripted-run fixture; `tests/test_exporter_swap.py` (AC4).
3. `harness run --backend local` against Bedrock and RODA, then `harness check` on that run (AC2 and AC3 live). **Commit.**

**Slice 3: Deploy** (needs confirmation before the account-wide step).
1. `infra/` CDK (Python): the bucket (retained), the ECR image asset (linux/arm64, `boot.sh`), the execution role, one runtime, the budget (`-c budget_email`), and tags.
2. Spike S2 on the deployed image: 100% archived, a real RODA `preview_dataset` call, a 13-minute call, a 16 KB attribute, ADOT `add_span_processor`.
3. Transaction Search, **after the user confirms**. Then `harness run` against AgentCore end to end (AC1, AC5 on S3), and a check that the spans are visible in CloudWatch. **Commit.**

**Slice 4: LGND Geo, suites and narrative.**
1. Spike S3 (LGND headless auth); add LGND to the agent if it passes.
2. `harness run --suite` with the cost guard and `suite.json`; the narrative call (ADR-3); `suites/dallas-dc-v1.yaml`.
3. Live: a 2 prompts × 2 models suite and `harness compare` (AC10, AC11). Spike S6 sets the prompt's bound. **Commit**, then the Verify stage.
