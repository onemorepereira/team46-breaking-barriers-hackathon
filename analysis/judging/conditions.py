"""Request conditions and evidence matrix. Saved data only; no network or model calls."""

from __future__ import annotations

import json
import re
from typing import Any

from analysis import provenance
from analysis.trace import Run
from core import geometry


def load(run: Run) -> dict[str, Any] | None:
    text = run.store.read_text(f"runs/{run.run_id}/conditions.json")
    return json.loads(text) if text else None


def records(data: Any) -> list[dict[str, Any]]:
    out = []
    if isinstance(data, dict):
        fields = {k.lower(): v for k, v in data.items()}
        if any(k in fields for k in ("lat", "latitude")) or fields.get("type") == "Feature":
            out.append(data)
        elif fields.get("type") == "Point":
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


def references(run: Run, feature: str) -> list[tuple[float, float, str]]:
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
                if k.lower()
                in ("lat", "latitude", "lon", "lng", "longitude", "type", "coordinates", "geometry")
            }
            for lat, lon in provenance._coordinate_pairs(location):
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    found.append((lat, lon, str(s.attr("harness.tool.ref"))))
    return found


def evaluate(run: Run, prov: provenance.Provenance | None = None) -> dict[str, Any] | None:
    saved = load(run)
    if saved is None or saved.get("status") == "not_checked":
        return None  # never infer conditions on replay of a legacy archive
    conditions = saved.get("conditions", [])
    rows: list[dict[str, Any]] = []
    area = (run.manifest.get("snapshot") or {}).get("search_area") or {}
    prov = prov if prov is not None else provenance.grade(run)
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
                candidates = [
                    (lat, lon, ref)
                    for lat, lon, ref in references(run, c["reference_feature"])
                    if geometry.distance_km(*pair, lat, lon) > 0.001
                ]
                if candidates:
                    distances = [(geometry.distance_km(*pair, lat, lon), ref) for lat, lon, ref in candidates]
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
    return {
        "conditions": conditions,
        "rows": rows,
        "error": saved.get("error"),
        "supported": supported,
        "total": len(cells),
        "score": (supported / len(cells) if cells else 0.0) if advanced else None,
        "needs_review": bool(saved.get("error"))
        or (advanced and not rows)
        or any(c["status"] != "supported" for c in cells),
    }
