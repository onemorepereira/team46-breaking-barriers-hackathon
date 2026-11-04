"""The span schema shared by the agent (which writes spans) and analysis (which reads them)."""

from __future__ import annotations

STRANDS_SCOPE = "strands.telemetry.tracer"  # spike S1
HARNESS_SCOPE = "harness"
AGENT_SCOPES = {STRANDS_SCOPE, HARNESS_SCOPE}

# harness.* decision span names
RUN_START = "harness.run.start"
RUN_END = "harness.run.end"
MODEL_RESULT = "harness.model_result"
TOOL_RESULT = "harness.tool_result"

SPAN_CAP_BYTES = 16 * 1024  # the most tool-result text kept on a span and shown to the model


def span_kind_for(name: str) -> str:
    """Map a span name to harness.span_kind (design ADR-2; names from spike S1)."""
    if name.startswith("harness."):
        return "harness"
    if name.startswith("invoke_agent"):
        return "agent"
    if name == "execute_event_loop_cycle":
        return "cycle"
    if name == "chat":
        return "model"
    if name.startswith("execute_tool"):
        return "tool"
    return "other"
