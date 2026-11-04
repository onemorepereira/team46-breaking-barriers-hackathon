"""Request conditions and evidence matrix. Saved data only; no network or model calls."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from typing import Any, NamedTuple

from analysis import provenance
from analysis.trace import Run
from core import geometry

UNREADABLE = "Saved request conditions could not be read"
_KINDS = ("target", "inside_area", "within_distance", "other")
_SHAPES = ("Polygon", "MultiPolygon")
_LOCATION_KEYS = ("centroid", "center", "centre", "location", "position", "geometry")


class Reference(NamedTuple):
    """A located feature: its point(s), any polygon it covers, and the tool step that returned it."""

    points: list[tuple[float, float]]
    shapes: list[dict[str, Any]]
    ref: str


def _well_formed(c: Any) -> bool:
    if not isinstance(c, dict) or c.get("kind") not in _KINDS:
        return False
    if not isinstance(c.get("id"), str) or not isinstance(c.get("text"), str):
        return False
    if c["kind"] != "within_distance":
        return True
    km = c.get("distance_km")
    return (
        isinstance(km, int | float)
        and not isinstance(km, bool)
        and math.isfinite(km)
        and km > 0
        and isinstance(c.get("reference_feature"), str)
    )


def load(run: Run) -> dict[str, Any] | None:
    """The saved conditions, or None for a legacy run. A damaged file reads as an extraction error,
    so the run's page stays available and Re-judge can replace the file."""
    text = run.store.read_text(f"runs/{run.run_id}/conditions.json")
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("conditions", []), list)
        or not all(_well_formed(c) for c in data.get("conditions", []))
    ):
        return {"conditions": [], "error": UNREADABLE}
    return data


def records(data: Any) -> list[dict[str, Any]]:
    out = []
    if isinstance(data, dict):
        fields = {k.lower(): v for k, v in data.items()}
        if any(k in fields for k in ("lat", "latitude", *_LOCATION_KEYS)) or fields.get("type") in (
            "Feature",
            "Point",
            *_SHAPES,
        ):
            out.append(data)
        cols, rows = data.get("columns"), data.get("rows")
        if isinstance(cols, list) and isinstance(rows, list):
            for row in rows:
                if isinstance(row, list):
                    out.extend(records(dict(zip(cols, row, strict=False))))
        for value in data.values():
            out.extend(records(value))
    elif isinstance(data, list):
        for value in data:
            out.extend(records(value))
    elif isinstance(data, str):
        try:
            nested = json.loads(data)
            if isinstance(nested, dict | list):
                out.extend(records(nested))
        except ValueError:
            pass
    return out


def _outline(shape: dict[str, Any]) -> Iterator[tuple[float, float]]:
    """Outer-ring vertices as (lat, lon). Skips anything malformed."""
    coords = shape.get("coordinates")
    polygons = coords if shape.get("type") == "MultiPolygon" else [coords]
    for rings in polygons if isinstance(polygons, list) else []:
        for vertex in rings[0] if isinstance(rings, list) and rings and isinstance(rings[0], list) else []:
            try:
                lat, lon = float(vertex[1]), float(vertex[0])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            yield lat, lon


def _inside(shape: dict[str, Any], lat: float, lon: float) -> bool:
    try:
        return geometry.contains(shape, lon, lat)
    except (TypeError, ValueError, IndexError, KeyError):
        return False


def references(run: Run, feature: str) -> list[Reference]:
    words = set(re.findall(r"[a-z]+", feature.lower())) - {"a", "an", "the", "of", "in"}
    found = []
    for s in run.tool_results:
        if s.attr("harness.tool.status") in ("error", None):
            continue
        text = run.tool_result_text(s) or str(s.attr("harness.tool.result", ""))
        try:
            data = json.loads(text)
        except ValueError:
            continue
        for r in records(data):
            fields = {k.lower(): v for k, v in r.items()}
            props = fields.get("properties")
            if isinstance(props, dict):
                fields.update({k.lower(): v for k, v in props.items()})
            label = " ".join(
                str(fields.get(k, "")) for k in ("name", "type", "label", "category", "description")
            )
            if (
                not words
                or not words <= set(re.findall(r"[a-z]+", label.lower()))
                or re.search(r"\b(?:not|unconfirmed|maybe|unknown)\b", label.lower())
            ):
                continue
            # Use the provenance parser's coordinate aliases and GeoJSON ordering, but only
            # this record's own location: never borrow coordinates from a nested child site.
            location = {
                k: v
                for k, v in r.items()
                if k.lower() in ("lat", "latitude", "lon", "lng", "longitude", "type", "coordinates")
                or k.lower() in _LOCATION_KEYS
            }
            shapes = [
                g for g in (r, fields.get("geometry")) if isinstance(g, dict) and g.get("type") in _SHAPES
            ]
            # The boundary is never farther away than its nearest vertex, so a vertex within
            # the limit proves the condition. A far vertex proves nothing, and stays unverified.
            points = [*provenance._coordinate_pairs(location), *(p for g in shapes for p in _outline(g))]
            points = [(lat, lon) for lat, lon in points if -90 <= lat <= 90 and -180 <= lon <= 180]
            if points:
                found.append(Reference(points, shapes, str(s.attr("harness.tool.ref"))))
    return found


def _own_points(run: Run, prov: provenance.Provenance) -> list[tuple[float, float]]:
    """Each claimed site's own record: the closest coordinate in its cited result that the claim
    matches within its rounding. A site's own record can't also be its reference feature."""
    spans = provenance._latest_attempts(run)
    own: list[tuple[float, float]] = []
    for claim in prov.claims:
        pair = geometry.coordinate_pair(claim.value)
        span = spans.get(claim.ref or "")
        if not pair or claim.status != provenance.MATCHED or span is None:
            continue
        text = run.tool_result_text(span) or str(span.attr("harness.tool.result", ""))
        try:
            data = json.loads(text)
        except ValueError:
            data = text
        matching = [
            p for p in provenance._coordinate_pairs(data) if provenance.coordinate_within(claim.value, *p)
        ]
        if matching:
            own.append(min(matching, key=lambda p: geometry.distance_km(*pair, *p)))
    return own


def _distance(
    pair: tuple[float, float], reference: Reference, own: list[tuple[float, float]]
) -> float | None:
    """Claim to reference in km, or None when the reference is only some claimed site's own record."""
    points = [
        p
        for p in reference.points
        if geometry.distance_km(*pair, *p) > 0.001 and all(geometry.distance_km(*o, *p) > 0.001 for o in own)
    ]
    if not points:
        return None
    if any(_inside(shape, *pair) for shape in reference.shapes):
        return 0.0
    return min(geometry.distance_km(*pair, *p) for p in points)


def evaluate(run: Run, prov: provenance.Provenance | None = None) -> dict[str, Any] | None:
    saved = load(run)
    if saved is None:
        return None  # never infer conditions on replay of a legacy archive
    conditions = saved.get("conditions", [])
    status_ = "not_checked" if saved.get("status") == "not_checked" else "checked"
    rows: list[dict[str, Any]] = []
    if not conditions:
        return {
            "status": status_,
            "conditions": [],
            "rows": rows,
            "error": saved.get("error"),
            "supported": 0,
            "total": 0,
            "score": None,
            "cap": None,
            "needs_review": bool(saved.get("error")),
        }
    area = (run.manifest.get("snapshot") or {}).get("search_area") or {}
    prov = prov if prov is not None else provenance.grade(run)
    own = _own_points(run, prov)
    located = {
        c["id"]: references(run, c["reference_feature"]) for c in conditions if c["kind"] == "within_distance"
    }
    for claim in prov.claims:
        pair = geometry.coordinate_pair(claim.value)
        if not pair:
            continue
        cells: list[dict[str, Any]] = []
        for c in conditions:
            kind = c["kind"]
            status, reason, refs = "unverified", "Needs a judge or human to check the evidence", []
            if claim.status != provenance.MATCHED:
                reason = "The claimed location could not be matched to a successful tool result"
            elif kind == "inside_area" and area.get("geometry"):
                inside = geometry.contains(area["geometry"], pair[1], pair[0])
                status = "supported" if inside else "contradicted"
                reason, refs = "Location compared with the saved requested boundary", [claim.ref]
            elif kind == "within_distance":
                distances = [
                    (d, r.ref) for r in located[c["id"]] if (d := _distance(pair, r, own)) is not None
                ]
                if distances:
                    distance, ref = min(distances)
                    if distance <= c["distance_km"]:
                        status, refs = "supported", [claim.ref, ref]
                    reason = (
                        f"Nearest evidenced reference point: {distance:.2f} km; "
                        "distance to the area's boundary was not measured"
                    )
                    if status == "unverified":
                        reason += "; no complete reference inventory proves that a nearer feature is absent"
                else:
                    reason = f"No located {c['reference_feature']} evidenced in successful tool results"
            cells.append({"condition_id": c["id"], "status": status, "reason": reason, "refs": refs})
        rows.append({"claim": claim.claim, "value": claim.value, "cells": cells})
    ids = {c["id"] for c in conditions if c["kind"] in ("inside_area", "within_distance")}
    cells = [cell for row in rows for cell in row["cells"] if cell["condition_id"] in ids]
    supported = sum(c["status"] == "supported" for c in cells)
    advanced = any(c["kind"] == "within_distance" for c in conditions)
    # The weakest condition sets the cap, so strong area coverage can't hide an unevidenced distance.
    coverage = [
        sum(c["status"] == "supported" for c in per) / len(per)
        for i in ids
        if (per := [c for c in cells if c["condition_id"] == i])
    ]
    return {
        "status": status_,
        "conditions": conditions,
        "rows": rows,
        "error": saved.get("error"),
        "supported": supported,
        "total": len(cells),
        "score": (supported / len(cells) if cells else 0.0) if advanced else None,
        "cap": (min(coverage) if coverage else 0.0) if advanced else None,
        "needs_review": bool(saved.get("error"))
        or (advanced and not rows)
        or any(c["status"] != "supported" for c in cells),
    }
