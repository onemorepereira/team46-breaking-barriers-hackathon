"""LGND Geo facts, from its MCP tool schemas (2026-11-04). Pure: no network, no SDK."""

from __future__ import annotations

from typing import Any

SERVER = "lgnd"
MCP_URL = "https://geo.lgnd.ai/mcp"
RESOURCE = MCP_URL  # OAuth resource indicator
RESOURCE_METADATA = "https://geo.lgnd.ai/.well-known/oauth-protected-resource/mcp"
TOOL_NAMES = {
    "user_identity_get",
    "user_alias_set",
    "search_place_find",
    "search_chip_lat_lon",
    "search_change_find",
    "search_similar_change_find",
    "discover_area_view",
    "discover_area_shift_find",
    "discover_space_zoom",
    "discover_time_zoom",
    "discover_node_compare",
    "toolbox_classifier_build",
    "toolbox_classifier_apply",
    "toolbox_classifier_list",
    "toolbox_classifier_get",
    "reasoning_imagery_check",
    "reasoning_chip_view",
    "reasoning_change_view",
}
# Tools whose scope reads `area` (box, circle or polygon ring); omitting it searches the whole index.
AREA_TOOLS = {
    "search_place_find",
    "search_change_find",
    "search_similar_change_find",
    "discover_area_view",
    "discover_area_shift_find",
    "toolbox_classifier_apply",
}


def reads_area(tool: str, args: dict[str, Any]) -> bool:
    """Does this call's scope read `area`? (classifier_apply ignores it when nodes or inside are given.)"""
    if tool not in AREA_TOOLS:
        return False
    return not (tool == "toolbox_classifier_apply" and (args.get("nodes") or args.get("inside")))


def dataset_from_args(tool: str, args: dict[str, Any]) -> str | None:
    """LGND tools name an imagery index in scope.index (e.g. naip); report it as lgnd:<index>."""
    scope = args.get("scope")
    if isinstance(scope, dict) and scope.get("index"):
        return f"{SERVER}:{scope['index']}"
    return None
