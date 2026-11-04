"""Parsing LGND Geo tool output: tables come back as {"columns": [...], "rows": [[...], ...]}. Pure."""

from __future__ import annotations

import json
from typing import Any


def _rows(table: Any) -> list[dict[str, Any]]:
    if not isinstance(table, dict) or not isinstance(table.get("rows"), list):
        return []
    cols = table.get("columns") or []
    return [dict(zip(cols, r, strict=False)) for r in table["rows"] if isinstance(r, list)]


def _json(result: str) -> dict[str, Any] | None:
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def index_of(node: Any) -> str | None:
    """'naip/obs:123' -> 'naip', 's2/f1.2021@all' -> 's2'."""
    return str(node).split("/", 1)[0] if node and "/" in str(node) else None


def _bbox_around(lat: float, lon: float, cell_km: float) -> list[float]:
    import math

    half_lat = cell_km / 2 / 111.32
    half_lon = cell_km / 2 / (111.32 * max(math.cos(math.radians(lat)), 1e-6))
    return [lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat]


def chips_of(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every located place in an LGND result, as {node, lat, lon, bbox, index, ...}.

    Places come as one top-level place (search_chip_lat_lon) or in three table shapes (2026-11-04 outputs):
    - `matches` (search tools): rows with lat, lon, bbox, chip_id, observed, similarity.
    - `results` (toolbox_classifier_apply): rows with lat, lon, bbox, label, margin, fit.
    - `cells` (discover_area_view and friends): rows with lat, lon; the box comes from the top-level cell_km.
    """
    chips: list[dict[str, Any]] = []
    if isinstance(data.get("lat"), int | float) and isinstance(data.get("bbox"), list) and data.get("node"):
        # search_chip_lat_lon: one place at the top level
        top = {k: data[k] for k in ("node", "observed") if data.get(k) is not None}
        chips.append(
            {
                **top,
                "lat": data["lat"],
                "lon": data["lon"],
                "bbox": data["bbox"],
                "index": index_of(data["node"]),
            }
        )
    cell_km = data.get("cell_km")
    for key in ("matches", "results", "cells"):
        for r in _rows(data.get(key)):
            lat, lon, bbox = r.get("lat"), r.get("lon"), r.get("bbox")
            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue
            if not (isinstance(bbox, list) and len(bbox) == 4):
                if not isinstance(cell_km, int | float):
                    continue
                bbox = _bbox_around(lat, lon, float(cell_km))
            chip = {
                k: r.get(k)
                for k in ("node", "chip_id", "observed", "similarity", "label")
                if r.get(k) is not None
            }
            chips.append({**chip, "lat": lat, "lon": lon, "bbox": bbox, "index": index_of(r.get("node"))})
    return chips


def extras(result: str) -> dict[str, Any]:
    """Chips (with bbox) and scope from any located result; per-chip verdicts from imagery checks."""
    data = _json(result)
    if data is None:
        return {}
    out: dict[str, Any] = {}
    if data.get("matches") is not None:
        out["where"] = data.get("where")
        out["unscoped"] = data.get("where") == "everywhere"
    elif data.get("area") or data.get("targets"):
        out["where"] = data.get("targets") or data.get("area")
    chips = chips_of(data)
    if chips:
        out["chips"] = chips
    verdicts = [
        {"node": r.get("node"), "answer": r.get("answer"), "reason": r.get("reason")}
        for r in _rows(data.get("places"))
        if r.get("node")
    ]
    if verdicts:
        out["verdicts"] = verdicts
        out["verdict"] = data.get("verdict")
    return out


def searched_everywhere(result: str) -> bool:
    """LGND answers a search with no scope.area with where='everywhere'."""
    data = _json(result)
    return bool(data) and data.get("where") == "everywhere"  # type: ignore[union-attr]
