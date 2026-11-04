# Spike results

## S1: Strands, locally (2026-11-03)

The setup was `strands-agents==1.63.0`, `mcp==2.3.0`, `opentelemetry-sdk==1.45.2`, Python 3.12, model `us.anthropic.claude-haiku-5-5` in us-west-2, and RODA `awslabs.roda-mcp-server@0.1.7` over stdio through `uvx`. Two live runs completed with `end_turn`: one in 16.9 s using 31k tokens, the other using 17k tokens. The code is in `spikes/s1/`.

| Question | Answer | Design impact |
| --- | --- | --- |
| Does `StrandsTelemetry(tracer_provider=p)` route Strands' spans to `p`? | **No.** Zero spans were captured until `trace.set_tracer_provider(p)` was also called. Strands' tracer reads the global provider. | `telemetry.py` sets the global provider once per process, then passes it to `StrandsTelemetry`. This fits the one-provider-per-process rule. |
| What's Strands' instrumentation scope name? | `strands.telemetry.tracer` (the module's `__name__`, used as `service_name` in `get_tracer`). The MCP library emits its own `MCP send …` CLIENT spans. | The agent-span filter is scope `strands.telemetry.tracer` plus `harness`. The `MCP send` spans are excluded. |
| What are the span names? | `invoke_agent Strands Agents`, `execute_event_loop_cycle`, `chat`, `execute_tool <tool>` | `harness.span_kind`: `invoke_agent*` → agent, `execute_event_loop_cycle` → cycle, `chat` → model, `execute_tool*` → tool |
| Where is message content? | In span **events**: `gen_ai.system.message`, `gen_ai.user.message`, `gen_ai.assistant.message`, `gen_ai.tool.message` and `gen_ai.choice`, with a JSON `content` or `message` attribute. Token usage is in attributes: `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`. | The archive keeps events. AC2 still uses our `harness.*` spans. |
| What does `AfterModelCallEvent` expose? | `stop_response` (a `ModelStopResponse` with `.message` and `.stop_reason`), `exception` and `retry`. The message's `metadata.usage` has the tokens and `metadata.metrics.latencyMs` the latency. Reasoning is at `message.content[].reasoningContent.reasoningText.text`, and was present on 3 of 4 calls. | Reasoning, usage and output are read from `stop_response`. No `agent.messages` fallback is needed. |
| What do `BeforeModelCallEvent` and `AfterToolCallEvent` add? | `BeforeModelCallEvent.projected_input_tokens` and `.cancel`. `AfterToolCallEvent.duration` (seconds), `.result` (`status`, `content`, `structuredContent`, `isError`) and `.retry`. Every `Before*` event has a `cancel` field. | The input cap uses `projected_input_tokens`; tool latency comes from `duration`; cooperative cancel uses `cancel`. |
| Does `BedrockModel` accept a client config? | Yes: `boto_client_config: botocore.config.Config`, plus `region_name`. | As designed. |
| What's the per-call MCP timeout? | `MCPClient` has only `startup_timeout`. `call_tool_async(..., read_timeout_seconds=)` exists, but `MCPAgentTool.stream` calls it without a timeout. | Use the design's fallback: a thin `AgentTool` wrapper that calls `call_tool_async` with `read_timeout_seconds=60`. |
| What does the default conversation manager do? | `SlidingWindowConversationManager(window_size=40, should_truncate_results=True)`. **It trims history.** `NullConversationManager` exists. | We must pass `conversation_manager=NullConversationManager()` (already in the design); the trim guard stays as a backstop. |
| Is a scripted model provider possible? | Yes. `strands.models.Model` is abstract with `get_config`, `update_config`, `stream` and `structured_output`; `stream` yields `StreamEvent`s. | The AC4 scripted provider subclasses `Model`. |
| What are RODA's tools? | `search_datasets(query, tags, organization, license_type, limit)`, `list_datasets(tag, limit)`, `get_dataset_details(slug)`, `discover_by_organization`, `discover_by_license`, `find_related_datasets(slug, limit)`, `get_knowledge_base_stats()`, `preview_dataset(slug, bucket_arn)`, `sample_dataset(slug, file_key, bucket_arn)`, `search_stac_endpoints(query, limit)` | `datasets.py`: the dataset ID is the `slug` argument, or each `results[].slug` in a search result |
| How does the model handle missing labels? | Without `[ref Tn]` labels, the model wrote `"ref": "not provided in tool output"` rather than inventing one. | Confirms the labels must be stamped by the hook. |

## S2: AgentCore Runtime, deployed (2026-11-03)

The stack is `Team46EvalHarness` (CDK, us-west-2): runtime `team46_eval_harness-VzYWReDy9h` and archive `s3://team46evalharness-archiveda4cb258-qgbj570ey9mw`. The image is linux/arm64, built with podman. Three real runs (`954835ff…`, `77151a3e…`, `572c67cc…`) each took about a minute and covered 16–22 steps.

| Question | Answer |
| --- | --- |
| Does ADOT's provider accept `add_span_processor`? | **Yes.** Our processors attach under `opentelemetry-instrument`, and every run archived to S3. |
| Can `uvx` start RODA in the runtime, with internet access? | **Yes.** Real `search_datasets`, `preview_dataset` and `sample_dataset` calls succeeded from the runtime (`PUBLIC` network mode), and the role's read-only S3 grant was enough for previews. |
| Are 100% of spans archived? | **Yes:** `harness.decision_spans_emitted` 18 = 18 harness spans archived (run `77151a3e`). `harness check` reported 0 missing fields on every deployed run. |
| Does ADOT add spans? | **Yes**, as the design predicted: scopes `mcp-python-sdk`, `opentelemetry.instrumentation.botocore.bedrock-runtime` and `…botocore.s3`. The agent-span filter excludes them. |
| Is content kept on the spans? | The decision spans carry full content in every mode. CloudWatch content wasn't inspected beyond counts. |
| Do spans reach CloudWatch? | **Yes, once Transaction Search was enabled** (user-approved; status ACTIVE). Run `572c67cc`'s trace has 98 spans in `aws/spans`. |
| Does a 13-minute synchronous call work? | **Not tested.** Real runs take about a minute. The documented background-task fallback (`HealthyBusy` through `BedrockAgentCoreApp.add_async_task`) stays the plan if long runs appear. |
| Does a 16 KB attribute reach CloudWatch? | **Not tested:** no tool result exceeded 16 KB in these runs. |
| What is the per-tool MCP timeout? | `MCPAgentTool.timeout` is passed as `read_timeout_seconds`, so the handler sets `tool.timeout = timedelta(seconds=60)` on every listed tool. No wrapper is needed (this corrects the S1 note). |
