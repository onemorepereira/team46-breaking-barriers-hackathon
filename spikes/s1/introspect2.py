# /// script
# requires-python = ">=3.12"
# dependencies = ["strands-agents[otel]", "mcp"]
# ///
import inspect
from strands import Agent
from strands.models import Model
from strands.models.bedrock import BedrockModel
import strands.telemetry.tracer as T
from strands.tools.mcp import MCPClient
from strands.tools.mcp.mcp_agent_tool import MCPAgentTool
a = Agent(model=BedrockModel(model_id="x", region_name="us-west-2"))
cm = a.conversation_manager
print("default CM:", type(cm).__name__, {k: v for k, v in vars(cm).items() if not k.startswith("_")})
print("Model abstract:", sorted(Model.__abstractmethods__))
print("Model.stream sig:", inspect.signature(Model.stream))
print("tracer module __name__:", T.__name__)
for n in ["call_tool_sync", "call_tool_async"]:
    f = getattr(MCPClient, n, None); print(n, inspect.signature(f) if f else None)
src = inspect.getsource(MCPAgentTool.stream); print("MCPAgentTool.stream calls:", [l.strip() for l in src.splitlines() if "call_tool" in l])
