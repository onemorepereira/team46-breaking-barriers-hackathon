"""LGND Geo MCP client over streamable HTTP, with a fresh access token from the stored refresh token."""

from __future__ import annotations

from typing import Any

from tools.lgnd.auth import access_token
from tools.lgnd.descriptors import MCP_URL


def make_client(secret_id: str, region: str, url: str = MCP_URL) -> Any:
    """Raises RuntimeError when there is no LGND login yet (run `harness lgnd-login`)."""
    from strands.tools.mcp import MCPClient

    token = access_token(secret_id, region) if secret_id else None
    if not token:
        raise RuntimeError("no LGND login; run `harness lgnd-login`")
    return MCPClient(url=url, headers={"authorization": f"Bearer {token}"})
