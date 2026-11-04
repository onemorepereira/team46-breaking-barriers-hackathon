"""One plain-English sentence per tool call, dispatched by MCP server. Pure (no clients, no network)."""

from __future__ import annotations

import json
from typing import Any

from tools.lgnd import describe as lgnd
from tools.lgnd.descriptors import SERVER as LGND
from tools.roda import describe as roda
from tools.roda.descriptors import SERVER as RODA

_BY_SERVER = {LGND: lgnd.describe, RODA: roda.describe}
SERVER_LABELS = {LGND: "LGND Geo", RODA: "AWS Open Data (RODA)"}


def describe(server: str | None, name: str, args: Any, result: str, status: str = "ok") -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    fn = _BY_SERVER.get(str(server))
    if fn is None:
        return f"Called {name}: {str(result)[:100].strip()}"
    return fn(name, args if isinstance(args, dict) else {}, str(result or ""), status)
