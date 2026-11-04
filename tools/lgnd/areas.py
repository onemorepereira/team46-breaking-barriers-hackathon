"""LGND Geo's polygon scope format: {"ring": [{"lat", "lon"}, ...]}."""

from __future__ import annotations

from typing import Any

from core.geometry import simplify


def ring_polygon(area: Any) -> dict[str, Any] | None:
    """The GeoJSON Polygon of an LGND `{"ring": [{lat, lon}, ...]}` scope, or None for another shape."""
    ring = area.get("ring") if isinstance(area, dict) else None
    if not isinstance(ring, list) or len(ring) < 3:
        return None
    try:
        pts = [[float(p["lon"]), float(p["lat"])] for p in ring]
    except (KeyError, TypeError, ValueError):
        return None
    return {"type": "Polygon", "coordinates": [pts + [pts[0]]]}


def to_lgnd_area(geometry: dict[str, Any], max_vertices: int = 500) -> dict[str, Any]:
    """LGND's polygon scope from the largest outer ring, simplified (Douglas-Peucker) to max_vertices.

    LGND takes one ring without holes, so a hole or a second part is ignored here; the inside/outside check on
    results still uses the full geometry.
    """
    polys = geometry["coordinates"] if geometry.get("type") == "MultiPolygon" else [geometry["coordinates"]]
    outer = max((p[0] for p in polys if p), key=len)
    ring = outer[:-1] if outer and outer[0] == outer[-1] else list(outer)
    tol = 0.0
    while len(ring) > max_vertices:
        tol = tol * 2 if tol else 1e-5
        ring = simplify(outer, tol)[:-1]
    return {"ring": [{"lat": round(p[1], 6), "lon": round(p[0], 6)} for p in ring]}
