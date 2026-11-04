"""RODA MCP client over stdio (Strands MCPClient, documented pattern; spike S1)."""

from __future__ import annotations

from typing import Any

from tools.roda.descriptors import PACKAGE


def make_client() -> Any:
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    params = StdioServerParameters(command="uvx", args=[PACKAGE])
    return MCPClient(lambda: stdio_client(params))  # type: ignore[arg-type,return-value]  # mcp 2.x stream types
