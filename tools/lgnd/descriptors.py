"""LGND Geo facts, from its MCP tool schemas (2026-11-04). Pure: no network, no SDK."""

from __future__ import annotations

from typing import Any

from core import geometry

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


def area_outline(area: Any) -> list[tuple[float, float]] | None:
    """Points (lon, lat) on the outline of an LGND scope area: a ring's vertices, 32 points round a circle,
    or a bbox's corners and edge midpoints. None for a shape we don't read (it is then never trusted)."""
    if not isinstance(area, dict):
        return None
    try:
        if isinstance(area.get("ring"), list) and area["ring"]:
            return [(float(p["lon"]), float(p["lat"])) for p in area["ring"]]
        if {"lat", "lon", "radius_km"} <= area.keys():
            lat, lon, r = float(area["lat"]), float(area["lon"]), float(area["radius_km"])
            ring = geometry.circle(lat, lon, r, n=32)["coordinates"][0]
            return [(x, y) for x, y in ring]
        if {"west", "east", "south", "north"} <= area.keys():
            w, e, s, n = (float(area[k]) for k in ("west", "east", "south", "north"))
            mx, my = (w + e) / 2, (s + n) / 2
            return [(w, s), (mx, s), (e, s), (e, my), (e, n), (mx, n), (w, n), (w, my)]
    except (KeyError, TypeError, ValueError):
        return None
    return None


def dataset_from_args(tool: str, args: dict[str, Any]) -> str | None:
    """LGND tools name an imagery index in scope.index (e.g. naip); report it as lgnd:<index>."""
    scope = args.get("scope")
    if isinstance(scope, dict) and scope.get("index"):
        return f"{SERVER}:{scope['index']}"
    return None
