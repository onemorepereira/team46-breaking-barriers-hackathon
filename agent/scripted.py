"""Test boundary fakes (HARNESS_TEST_SCRIPT): a scripted model in place of Bedrock and a local tool in
place of MCP. Everything else in a scripted run is the real code path (design ADR-2)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from strands import tool
from strands.models import Model

FACILITY = {
    "name": "DA11",
    "operator": "Equinix",
    "address": "1950 N Stemmons Fwy",
    "lat": 32.8008,
    "lon": -96.8195,
}


@tool
def lookup_facility(name: str) -> str:
    """Look up a data center facility by name."""
    return json.dumps({"results": [FACILITY if name == "DA11" else {}]})


class ScriptedModel(Model):
    """Replays a fixed list of turns: {"tool": name, "input": {...}} or {"text": "..."}."""

    def __init__(self, turns: list[dict[str, Any]]) -> None:
        self.turns = turns
        self.i = 0
        self.config: dict[str, Any] = {"model_id": "scripted"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:  # pragma: no cover
        raise NotImplementedError
        yield

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kw: Any
    ) -> Any:
        turn = self.turns[min(self.i, len(self.turns) - 1)]
        self.i += 1
        yield {"messageStart": {"role": "assistant"}}
        if turn.get("reasoning"):
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"reasoningContent": {"text": turn["reasoning"]}}}}
            yield {"contentBlockStop": {}}
        if "tool" in turn:
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": f"tooluse_s{self.i}", "name": turn["tool"]}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(turn.get("input", {}))}}}}
            yield {"contentBlockStop": {}}
            stop = "tool_use"
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": turn.get("text", "")}}}
            yield {"contentBlockStop": {}}
            stop = "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": 100,
                    "outputTokens": 20,
                    "totalTokens": 120,
                    "cacheReadInputTokens": 50 if self.i > 1 else 0,
                },
                "metrics": {"latencyMs": 5},
            }
        }
