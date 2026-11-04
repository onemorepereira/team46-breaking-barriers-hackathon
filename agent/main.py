"""AgentCore Runtime entry point: HTTP on 8080 at /invocations and /ping (HTTP protocol contract)."""

from __future__ import annotations

from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.handler import handle

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    return handle(payload)


if __name__ == "__main__":
    app.run()
