# /// script
# requires-python = ">=3.12"
# dependencies = ["strands-agents", "strands-agents[otel]", "mcp"]
# ///
"""Spike S1, part 1: introspect the installed Strands API (no network calls)."""
import dataclasses, importlib.metadata as md, inspect
for pkg in ["strands-agents", "mcp", "opentelemetry-sdk"]:
    try: print(f"{pkg}=={md.version(pkg)}")
    except Exception as e: print(pkg, "not installed", e)
import strands.hooks as H
print("\n== hook events in strands.hooks:")
for name in sorted(n for n in dir(H) if n.endswith("Event")):
    cls = getattr(H, name)
    flds = [f.name for f in dataclasses.fields(cls)] if dataclasses.is_dataclass(cls) else "n/a"
    print(f"  {name}: {flds}")
    w = getattr(cls, "_can_write", None)
    if callable(w):
        print("     writable:", [f for f in (flds if isinstance(flds, list) else []) if w(cls, f) if True] if False else "")
from strands.models.bedrock import BedrockModel
print("\n== BedrockModel.__init__", inspect.signature(BedrockModel.__init__))
print("   BedrockConfig keys:", list(getattr(BedrockModel, "BedrockConfig").__annotations__))
from strands.tools.mcp import MCPClient
print("\n== MCPClient.__init__", inspect.signature(MCPClient.__init__))
import strands.agent.conversation_manager as CM
print("\n== conversation managers:", [n for n in dir(CM) if "Manager" in n])
from strands import Agent
print("\n== Agent.__init__ params:", list(inspect.signature(Agent.__init__).parameters))
import strands.models as M
print("\n== strands.models:", [n for n in dir(M) if not n.startswith("_")])
from strands.telemetry import StrandsTelemetry
print("\n== StrandsTelemetry.__init__", inspect.signature(StrandsTelemetry.__init__))
import strands.telemetry.tracer as T
src = inspect.getsource(T)
import re
print("\n== tracer scope names:", sorted(set(re.findall(r'get_tracer\(\s*["\']([^"\']+)', src))), re.findall(r'get_tracer\(([^)]*)\)', src)[:3])
