# /// script
# requires-python = ">=3.12"
# dependencies = ["strands-agents[otel]", "mcp"]
# ///
"""Spike S1, part 2: one live local run (Bedrock + RODA over stdio) with probes."""
import inspect, json, os, sys, time
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from botocore.config import Config
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.agent.conversation_manager import NullConversationManager
from strands.hooks import HookProvider, HookRegistry, AfterModelCallEvent, AfterToolCallEvent, BeforeModelCallEvent, BeforeToolCallEvent
from strands.models import Model
from strands.models.bedrock import BedrockModel
from strands.telemetry import StrandsTelemetry
from strands.tools.mcp import MCPClient
import strands.telemetry.tracer as T

out = sys.argv[1]
spans_f = open(f"{out}/spans.jsonl", "w")
provider = TracerProvider(sampler=ALWAYS_ON)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=spans_f, formatter=lambda s: s.to_json(indent=None) + "\n")))
from opentelemetry import trace as _t; _t.set_tracer_provider(provider); StrandsTelemetry(tracer_provider=provider)
print("default conversation manager:", type(Agent(model=BedrockModel(model_id="x")).conversation_manager).__name__)
print("Model abstract methods:", sorted(getattr(Model, "__abstractmethods__", [])))
print("tracer service_name default:", [l.strip() for l in inspect.getsource(T).splitlines() if "service_name" in l][:4])
probe = open(f"{out}/hooks.jsonl", "w")
def dump(obj, n=1500):
    try: return json.dumps(obj, default=str)[:n]
    except Exception as e: return f"<unserializable {e}>"
class Probe(HookProvider):
    def register_hooks(self, r: HookRegistry, **kw):
        r.add_callback(BeforeModelCallEvent, lambda e: probe.write(dump({"ev":"before_model","projected_input_tokens":e.projected_input_tokens,"n_messages":len(e.agent.messages)})+"\n"))
        r.add_callback(AfterModelCallEvent, lambda e: probe.write(dump({"ev":"after_model","stop_response_type":type(e.stop_response).__name__,"stop_response":getattr(e,"stop_response",None).__dict__ if e.stop_response else None,"exception":str(e.exception)}, 6000)+"\n"))
        r.add_callback(BeforeToolCallEvent, lambda e: probe.write(dump({"ev":"before_tool","tool_use":e.tool_use})+"\n"))
        r.add_callback(AfterToolCallEvent, lambda e: probe.write(dump({"ev":"after_tool","tool_use_id":e.tool_use.get("toolUseId"),"duration":e.duration,"result_keys":list(e.result.keys()),"result":e.result}, 2500)+"\n"))
roda = MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.roda-mcp-server@0.1.7"])))
model = BedrockModel(model_id="us.anthropic.claude-haiku-5-5", region_name="us-west-2", max_tokens=16000,
    additional_request_fields={"thinking":{"type":"adaptive","display":"summarized"},"output_config":{"effort":"high"}},
    boto_client_config=Config(connect_timeout=10, read_timeout=120, retries={"mode":"standard","max_attempts":3}))
with roda:
    tools = roda.list_tools_sync()
    json.dump([{"name": t.tool_name, "spec": t.tool_spec} for t in tools], open(f"{out}/roda_tools.json","w"), default=str, indent=1)
    agent = Agent(model=model, tools=tools, hooks=[Probe()], conversation_manager=NullConversationManager(),
                  system_prompt="You find public datasets. Use tools. Be brief. End with a JSON claims block citing the [ref Tn] label of the tool result each value came from.")
    t0=time.time(); res = agent("Search the Registry of Open Data for datasets about building footprints in the United States. Name two dataset IDs.")
    print("run seconds:", round(time.time()-t0,1)); print("stop:", res.stop_reason); print("usage:", res.metrics.accumulated_usage)
provider.force_flush()
