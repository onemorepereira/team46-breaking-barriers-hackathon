"""LGND Geo MCP client over streamable HTTP, with an access token kept fresh from the stored refresh token."""

from __future__ import annotations

from typing import Any

from tools.lgnd.auth import RefreshingBearer, access_token
from tools.lgnd.descriptors import MCP_URL


def make_client(secret_id: str, region: str, url: str = MCP_URL) -> Any:
    """Raises RuntimeError when there is no LGND login yet (run `harness lgnd-login`)."""
    from strands.tools.mcp import MCPClient

    token = access_token(secret_id, region) if secret_id else None
    if not token:
        raise RuntimeError("no LGND login; run `harness lgnd-login`")
    # Tokens live 300 s: refresh them for the whole run, not once at startup (see RefreshingBearer).
    auth = RefreshingBearer(lambda: access_token(secret_id, region), token)
    return MCPClient(url=url, auth_provider=auth)
