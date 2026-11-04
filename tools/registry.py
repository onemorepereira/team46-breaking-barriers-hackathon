"""Builds the agent's tools: every configured MCP server's tools, each with a per-call timeout.

Returns (tools, server_of, available): server_of maps tool name -> server id; available is what
harness.run.start records (server, tool, input_schema), including a server that failed to start.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import timedelta
from typing import Any

from tools.lgnd import client as lgnd_client
from tools.lgnd.descriptors import SERVER as LGND
from tools.roda import client as roda_client
from tools.roda.descriptors import SERVER as RODA

log = logging.getLogger("harness.tools")


def build(
    stack: ExitStack,
    *,
    timeout_s: int,
    region: str,
    lgnd_url: str | None = None,
    lgnd_secret_id: str | None = None,
) -> tuple[list[Any], dict[str, str], list[dict[str, Any]]]:
    servers: list[tuple[str, Any]] = []
    available: list[dict[str, Any]] = []
    roda = roda_client.make_client()
    stack.enter_context(roda)
    servers.append((RODA, roda))
    if lgnd_url:
        try:
            lgnd = lgnd_client.make_client(lgnd_secret_id or "", region, lgnd_url)
            stack.enter_context(lgnd)
            servers.append((LGND, lgnd))
        except Exception as e:  # noqa: BLE001 - LGND is optional; record and continue with RODA
            log.warning("LGND Geo unavailable: %s", e)
            available.append({"server": LGND, "tool": None, "error": str(e)})
    tools: list[Any] = []
    server_of: dict[str, str] = {}
    for server, client in servers:
        for t in client.list_tools_sync():
            t.timeout = timedelta(seconds=timeout_s)  # MCPAgentTool passes this as read_timeout_seconds
            tools.append(t)
            server_of[t.tool_name] = server
            schema = (t.tool_spec.get("inputSchema") or {}).get("json", {})
            available.append({"server": server, "tool": t.tool_name, "input_schema": schema})
    return tools, server_of, available
