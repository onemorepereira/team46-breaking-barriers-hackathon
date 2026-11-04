"""Reference sets and the benchmark's matching rule (docs/adb-alignment/design.md). Pure: no I/O but reading a
set.

The unit is the asset. Models (here: an agent's located claims) flag 160 m grid cells; an asset is found
when any flagged cell touches it, and counts once. Recall, count ratio and lift are defined only for
complete references."""

from __future__ import annotations

import functools
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import geometry

R_EARTH_M = 6_371_008.8
# whole SPDX-style tokens only: "CC-BY-NC-4.0" and "CC-BY-ND-4.0" are refused; "LGND-..." and "ODbL" are not
BAD_LICENCE_RE = re.compile(
    r"(?:^|[-_ ])(?:NC|ND)(?:[-_ ]|$)|non[- ]?commercial|no[- ]?derivatives?|academic", re.I
)
Cell = tuple[int, int]


class ReferenceError(ValueError):
    """A reference set that can't be used; the message names the field."""


@dataclass
class Reference:
    id: str
    concept: str
    place: str
    area: dict[str, Any]
    completeness: str
    completeness_note: str
    source: dict[str, Any]
    licence: dict[str, Any]
    cell_m: float
    features: list[dict[str, Any]]
    sha256: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.completeness == "complete"

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "concept": self.concept,
            "place": self.place,
            "completeness": self.completeness,
            "completeness_note": self.completeness_note,
            "source": self.source,
            "licence": self.licence,
            "cell_m": self.cell_m,
            "area_source": self.meta.get("area_source"),
            "area_licence": self.meta.get("area_licence"),
            "assets": len(self.features),
            "sha256": self.sha256,
        }


def _need(d: dict[str, Any], key: str, where: str) -> Any:
    if d.get(key) in (None, "", [], {}):
        raise ReferenceError(f"{where}: `{key}` is required")
    return d[key]


def parse(meta: dict[str, Any], features_geojson: dict[str, Any], features_bytes: bytes) -> Reference:
    """Validate a reference record and its features (design: Reference sets)."""
    where = f"reference {meta.get('id', '?')}"
    for k in ("id", "concept", "place", "area", "completeness", "source", "licence"):
        _need(meta, k, where)
    if meta["completeness"] not in ("complete", "incomplete"):
        raise ReferenceError(f"{where}: `completeness` must be complete or incomplete")
    lic = meta["licence"]
    if not isinstance(lic, dict):
        raise ReferenceError(f"{where}: `licence` must be an object")
    for k in ("id", "name", "url"):
        _need(lic, k, f"{where} licence")
    if lic.get("commercial_use_ok") is not True:
        raise ReferenceError(
            f"{where}: `licence.commercial_use_ok` must be true (no non-commercial reference data)"
        )
    if BAD_LICENCE_RE.search(f"{lic['id']} {lic['name']}"):
        raise ReferenceError(f"{where}: licence {lic['id']!r} is non-commercial or academic-only")
    area = meta["area"]
    if not isinstance(area, dict) or area.get("type") not in ("Polygon", "MultiPolygon"):
        raise ReferenceError(f"{where}: `area` must be a GeoJSON Polygon or MultiPolygon")
    feats = [
        f for f in (features_geojson or {}).get("features") or [] if isinstance(f, dict) and f.get("geometry")
    ]
    if not feats:
        raise ReferenceError(f"{where}: features.geojson has no features")
    for i, f in enumerate(feats):
        if f["geometry"].get("type") not in ("Point", "Polygon", "MultiPolygon"):
            raise ReferenceError(f"{where}: feature {i} must be a Point, Polygon or MultiPolygon")
    del features_bytes  # hashed as parsed canonical JSON, so line endings don't change the sha
    sha = sha256_of(meta, features_geojson)
    cell_m = float(meta.get("cell_m") or 160)
    return Reference(
        str(meta["id"]),
        str(meta["concept"]),
        str(meta["place"]),
        area,
        meta["completeness"],
        str(meta.get("completeness_note", "")),
        meta["source"],
        lic,
        cell_m,
        feats,
        sha,
        meta,
    )


def sha256_of(meta: dict[str, Any], features_geojson: dict[str, Any]) -> str:
    canon = lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"))  # noqa: E731
    return hashlib.sha256(f"{canon(meta)}\n{canon(features_geojson)}".encode()).hexdigest()


def load(directory: str | Path) -> Reference:
    d = Path(directory)
    meta_p, feat_p = d / "reference.json", d / "features.geojson"
    if not meta_p.is_file() or not feat_p.is_file():
        raise ReferenceError(f"reference {d.name} not found (needs reference.json and features.geojson)")
    raw = feat_p.read_bytes()
    try:
        return parse(json.loads(meta_p.read_text(encoding="utf-8")), json.loads(raw), raw)
    except json.JSONDecodeError as e:
        raise ReferenceError(f"reference {d.name}: invalid JSON ({e})") from e


# ---- The grid ----


def _rings(geom: dict[str, Any]) -> list[list[list[list[float]]]]:
    """Polygon / MultiPolygon -> list of polygons, each a list of rings of [lon, lat]."""
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def _bbox(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    pts = [p for poly in _rings(geom) for ring in poly for p in ring]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


@dataclass(frozen=True)
class Grid:
    """A local equirectangular grid of `cell_m` cells anchored at the area's south-west corner."""

    lon0: float
    lat0: float
    kx: float  # metres per degree of longitude at the middle latitude
    ky: float  # metres per degree of latitude
    cell_m: float

    @classmethod
    def for_area(cls, area: dict[str, Any], cell_m: float) -> Grid:
        w, s, _, n = _bbox(area)
        mid = math.radians((s + n) / 2)
        ky = R_EARTH_M * math.pi / 180
        return cls(w, s, ky * math.cos(mid), ky, cell_m)

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def cell(self, lon: float, lat: float) -> Cell:
        x, y = self.xy(lon, lat)
        return math.floor(x / self.cell_m), math.floor(y / self.cell_m)

    def corners(self, c: Cell) -> list[tuple[float, float]]:
        """(lon, lat) corners of a cell, counter-clockwise from south-west."""
        i, j = c
        xs, ys = (i * self.cell_m, (i + 1) * self.cell_m), (j * self.cell_m, (j + 1) * self.cell_m)
        to = lambda x, y: (self.lon0 + x / self.kx, self.lat0 + y / self.ky)  # noqa: E731
        return [to(xs[0], ys[0]), to(xs[1], ys[0]), to(xs[1], ys[1]), to(xs[0], ys[1])]

    def cell_polygon(self, c: Cell) -> dict[str, Any]:
        ring = [list(p) for p in self.corners(c)]
        return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


def _centre_scanline(grid: Grid, geom: dict[str, Any]) -> Any:
    """Yield (j, first_i, last_i) runs of cells whose centre lies in the geometry (even-odd, all rings)."""
    w, s, e, n = _bbox(geom)
    (i0, j0), (i1, j1) = grid.cell(w, s), grid.cell(e, n)
    rings = [[grid.xy(p[0], p[1]) for p in ring] for poly in _rings(geom) for ring in poly]
    for j in range(j0, j1 + 1):
        yc = (j + 0.5) * grid.cell_m
        xs: list[float] = []
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
                if (y1 > yc) != (y2 > yc):
                    xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2], strict=False):
            first = max(i0, math.ceil(a / grid.cell_m - 0.5))
            last = min(i1, math.floor(b / grid.cell_m - 0.5))
            if last >= first:
                yield j, first, last


def asset_cells(grid: Grid, geom: dict[str, Any]) -> set[Cell]:
    """Every cell a Point/Polygon/MultiPolygon touches: interior cells (centre inside, by scanline), plus the
    cells each edge passes through (walked at 1/16 of a cell) and each vertex's cell (design: Performance)."""
    if geom["type"] == "Point":
        lon, lat = geom["coordinates"][:2]
        return {grid.cell(float(lon), float(lat))}
    out = {(i, j) for j, a, b in _centre_scanline(grid, geom) for i in range(a, b + 1)}
    step = grid.cell_m / 16
    for poly in _rings(geom):
        for ring in poly:
            pts = [grid.xy(p[0], p[1]) for p in ring]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=True):
                n = max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / step))
                for k in range(n + 1):
                    x, y = x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n
                    out.add((math.floor(x / grid.cell_m), math.floor(y / grid.cell_m)))
    return out


def count_area_cells(grid: Grid, geom: dict[str, Any]) -> int:
    """Cells whose centre lies in the area (holes and every part respected), counted exactly by scanline."""
    return sum(b - a + 1 for _, a, b in _centre_scanline(grid, geom))


@functools.lru_cache(maxsize=4096)
def _asset_cells_cached(sha: str, k: int, grid: Grid, geom_json: str) -> frozenset[Cell]:
    del sha, k  # part of the cache key only
    return frozenset(asset_cells(grid, json.loads(geom_json)))


@functools.lru_cache(maxsize=32)
def _area_cells_cached(sha: str, grid: Grid, area_json: str) -> int:
    """Area cells per reference version: the scanline runs once per process, not on every view."""
    del sha  # part of the cache key only
    return count_area_cells(grid, json.loads(area_json))


def in_area(grid: Grid, geom: dict[str, Any], c: Cell) -> bool:
    i, j = c
    x, y = (i + 0.5) * grid.cell_m, (j + 0.5) * grid.cell_m
    return geometry.contains(geom, grid.lon0 + x / grid.kx, grid.lat0 + y / grid.ky)


def projected_area_m2(grid: Grid, geom: dict[str, Any]) -> float:
    total = 0.0
    for poly in _rings(geom):
        for k, ring in enumerate(poly):
            pts = [grid.xy(p[0], p[1]) for p in ring]
            a = (
                abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=True)))
                / 2
            )
            total += a if k == 0 else -a
    return total


def sites(cells: set[Cell]) -> list[set[Cell]]:
    """Connected components of cells, 8-neighbour: neighbouring flagged cells are one site."""
    left, out = set(cells), []
    while left:
        stack, comp = [left.pop()], set()
        while stack:
            i, j = stack.pop()
            comp.add((i, j))
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (i + di, j + dj)
                    if nb in left:
                        left.remove(nb)
                        stack.append(nb)
        out.append(comp)
    return out


def score(ref: Reference, claims: list[tuple[float, float]]) -> dict[str, Any]:
    """Score located claims (lat, lon) against a reference with the benchmark's unit and matching rule."""
    grid = Grid.for_area(ref.area, ref.cell_m)
    occupied: dict[str, frozenset[Cell]] = {}
    outside_assets = []
    for k, f in enumerate(ref.features):
        rid = str((f.get("properties") or {}).get("ref_id") or k)
        cells = _asset_cells_cached(ref.sha256, k, grid, json.dumps(f["geometry"]))
        if any(in_area(grid, ref.area, c) for c in cells):
            occupied[rid] = cells
        else:
            outside_assets.append(rid)  # an asset counts only if one of its cells is an area cell
    all_asset = set().union(*occupied.values()) if occupied else set()
    asset_area_cells = {c for c in all_asset if in_area(grid, ref.area, c)}
    # flagged cells are area cells (centre in the area), the same population as area_cells and the asset cells
    # behind the base rate; a claim whose cell isn't an area cell counts as outside the area
    inside = [(lat, lon) for lat, lon in claims if in_area(grid, ref.area, grid.cell(lon, lat))]
    flagged = {grid.cell(lon, lat) for lat, lon in inside}
    found = sorted(rid for rid, cs in occupied.items() if cs & flagged)
    missed = sorted(rid for rid in occupied if rid not in set(found))
    hits = flagged & asset_area_cells
    n_assets = len(occupied)
    area_cells = max(1, _area_cells_cached(ref.sha256, grid, json.dumps(ref.area)))
    base_rate = len(asset_area_cells) / area_cells  # numerator and denominator: the same area-cell set
    precision = len(hits) / len(flagged) if flagged else None
    notes = []
    if not flagged:
        notes.append("no located sites inside the reference area to check")
    recall = count_ratio = lift = None
    if ref.complete and n_assets:
        recall = len(found) / n_assets
        count_ratio = len(sites(flagged)) / n_assets
        lift = precision / base_rate if precision is not None and base_rate > 0 else None
    else:
        notes.append("reference is incomplete: recall, count ratio and lift are undefined; precision only")
    return {
        "site_recall": None if recall is None else round(recall, 3),
        "cell_precision": None if precision is None else round(precision, 3),
        "count_ratio": None if count_ratio is None else round(count_ratio, 3),
        "lift": None if lift is None else round(lift, 1),
        "assets": n_assets,
        "assets_outside_area": outside_assets,
        "found": found,
        "missed": missed,
        "flagged_cells": len(flagged),
        "sites": len(sites(flagged)),
        "claims_scored": len(inside),
        "outside_area": len(claims) - len(inside),
        "area_cells": area_cells,
        "base_rate": round(base_rate, 6),
        "false_alarm_cells": [grid.cell_polygon(c) for c in sorted(flagged - asset_area_cells)],
        "notes": notes,
    }


# ---- A run's reference: the snapshot in its own archive (design: The tie) ----

SNAPSHOT = "reference"


def from_run(
    run: Any,
    claims: list[tuple[float, float]],
    claims_block_missing: bool = False,
    repo_sha: str | None = None,
) -> dict[str, Any] | None:
    """Score a run against the reference snapshot in its archive; None when untied. Reads only the run's
    store, so replay reproduces it and a rebuilt repo set never changes an old run's metrics."""
    base = f"runs/{run.run_id}/{SNAPSHOT}"
    tie_text = run.store.read_text(f"{base}/tie.json")
    if not tie_text:
        return None
    try:
        tie = json.loads(tie_text)
        meta_text, feat_text = (
            run.store.read_text(f"{base}/reference.json"),
            run.store.read_text(f"{base}/features.geojson"),
        )
        if not meta_text or not feat_text:
            raise ReferenceError("the reference snapshot is missing from the run's archive")
        ref = parse(json.loads(meta_text), json.loads(feat_text), b"")
    except (ReferenceError, json.JSONDecodeError) as e:
        return {
            "id": (json.loads(tie_text) if tie_text.strip().startswith("{") else {}).get("id"),
            "error": str(e),
        }
    out = {
        **ref.summary(),
        **score(ref, claims),
        "tied": tie,
        "stale": repo_sha is not None and repo_sha != ref.sha256,
    }
    if claims_block_missing:
        out["notes"].insert(0, "the answer had no claims block, so nothing could be located")
    found = set(out["found"])
    out["features"] = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    **(f.get("properties") or {}),
                    "found": str((f.get("properties") or {}).get("ref_id")) in found,
                },
            }
            for f in ref.features
        ],
    }
    return out
