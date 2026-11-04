"""Geometry math in lon/lat degrees: point-in-polygon, circles, polyline simplification. Stdlib only."""

from __future__ import annotations

import math
import re
from typing import Any


def circle(lat: float, lon: float, radius_km: float, n: int = 64) -> dict[str, Any]:
    ring = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        dlat = radius_km / 111.32 * math.cos(a)
        dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 1e-6)) * math.sin(a)
        ring.append([lon + dlon, lat + dlat])
    return {"type": "Polygon", "coordinates": [ring]}


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def contains(geometry: dict[str, Any], lon: float, lat: float) -> bool:
    """Point in Polygon/MultiPolygon; the first ring is the outline, the rest are holes."""
    polys = geometry["coordinates"] if geometry.get("type") == "MultiPolygon" else [geometry["coordinates"]]
    for rings in polys:
        if rings and _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, h) for h in rings[1:]):
            return True
    return False


def coordinate_pair(value: str) -> tuple[float, float] | None:
    """A claim value like '32.965, -96.7121' -> (lat, lon), or None."""
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", value or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def _perp_dist(p: list[float], a: list[float], b: list[float]) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def simplify(points: list[list[float]], tol: float) -> list[list[float]]:
    """Douglas-Peucker on an open polyline."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0.0, -1
        for k in range(i + 1, j):
            d = _perp_dist(points[k], points[i], points[j])
            if d > best:
                best, idx = d, k
        if idx != -1 and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(points, keep, strict=True) if k]
