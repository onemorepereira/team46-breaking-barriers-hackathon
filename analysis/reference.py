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


# ---- Ranking metrics (docs/ranking-metrics): the run's ranked candidates, not only its reported sites ----

Candidate = tuple[float, float, float, str]  # (lat, lon, similarity, the tool call it came from)
RECALL_AT = (10, 20, 50)
EFFORT_AT = (50, 80, 90)


def rank_cells(grid: Grid, area: dict[str, Any], claims: list[tuple[float, float]],
               chips: list[Candidate]) -> list[Cell]:  # fmt: skip
    """The run's ranked area cells: claims in answer order, then search results. Similarities aren't
    comparable across calls, so each call's results are ranked by descending similarity (ties keep first-seen
    order) and the calls are interleaved round-robin, in the order they were made. Each cell counts once, at
    its first rank; cells outside the area are skipped."""
    calls: dict[str, list[Candidate]] = {}
    for c in chips:
        calls.setdefault(c[3], []).append(c)

    # the order calls were made: refs are numbered when a call starts (T1, T2, ...); results arrive in
    # completion order, which differs for parallel calls. Refs without a number go last, in arrival order.
    def made(item: tuple[int, str]) -> tuple[int, int]:
        pos, ref = item
        m = re.fullmatch(r"T(\d+)", ref)
        return (int(m.group(1)), pos) if m else (10**9, pos)

    ordered = sorted(enumerate(calls), key=made)
    queues = [sorted(calls[ref], key=lambda c: -c[2]) for _, ref in ordered]  # stable sort
    order = [(lat, lon) for lat, lon in claims]
    for depth in range(max((len(q) for q in queues), default=0)):
        order += [(q[depth][0], q[depth][1]) for q in queues if depth < len(q)]
    out: list[Cell] = []
    seen: set[Cell] = set()
    for lat, lon in order:
        cell = grid.cell(lon, lat)
        if cell in seen or not in_area(grid, area, cell):
            continue
        seen.add(cell)
        out.append(cell)
    return out


def ranking_metrics(ranked: list[Cell], cell_assets: dict[Cell, set[str]], n_assets: int,
                    positives: set[Cell], area_cells: int, complete: bool) -> dict[str, Any]:  # fmt: skip
    """recall@k, AUROC, AP and review effort over a ranking of area cells (spec AC3-AC5).

    Positives are area cells touched by a reference asset; every other area cell is negative. Unranked cells
    are tied below the ranked ones: in AUROC a positive-negative tie counts half, and unranked positives add
    nothing to AP. recall@k and review effort count assets (any-touch, each once) and need a complete set."""
    P = len(positives)
    N = max(0, area_cells - P)
    notes: list[str] = []
    if not ranked:
        notes.append("no ranked candidates inside the reference area")
    # one pass: positives/negatives seen, assets found, AP sum, effort ranks, recall at fixed k
    found: set[str] = set()
    pos_seen = neg_seen = 0
    ap_sum = 0.0
    pos_ranks_neg_before: list[int] = []
    effort: dict[int, int | None] = {p: None for p in EFFORT_AT}
    recall_at: dict[int, float] = {}
    k_default = P
    recall_k_default: float | None = None
    for rank, c in enumerate(ranked, start=1):
        if c in positives:
            pos_seen += 1
            ap_sum += pos_seen / rank
            pos_ranks_neg_before.append(neg_seen)
        else:
            neg_seen += 1
        found |= cell_assets.get(c, set())
        share = len(found) / n_assets if n_assets else 0.0
        for p in EFFORT_AT:
            if effort[p] is None and n_assets and len(found) * 100 >= p * n_assets:  # exact, no float cut-off
                effort[p] = rank
        if rank in RECALL_AT:
            recall_at[rank] = share
        if rank == k_default:
            recall_k_default = share
    final_share = len(found) / n_assets if n_assets else 0.0
    for k in RECALL_AT:  # shorter lists: everything ranked is inside the top k
        recall_at.setdefault(k, final_share)
    if recall_k_default is None:
        recall_k_default = final_share
    ranked_neg = neg_seen
    # area_cells (scanline) and in_area can disagree on a boundary cell: never let a count go negative
    unranked_pos, unranked_neg = max(0, P - pos_seen), max(0, N - ranked_neg)
    auroc = ap = None
    pos_total, neg_total = pos_seen + unranked_pos, ranked_neg + unranked_neg  # effective counts after clamps
    if pos_total and neg_total:
        wins = sum((ranked_neg - before) + unranked_neg for before in pos_ranks_neg_before)
        auroc = (wins + 0.5 * unranked_pos * unranked_neg) / (pos_total * neg_total)
    if P:
        ap = ap_sum / P
    else:
        notes.append("no reference assets inside the area")
    r3 = lambda v: None if v is None else round(v, 3)  # noqa: E731
    out: dict[str, Any] = {
        "candidates": len(ranked), "positives": P, "negatives": N, "k": k_default,
        "auroc": r3(auroc), "ap": r3(ap),
        "random_effort": {str(p): math.ceil(p / 100 * area_cells) for p in EFFORT_AT},
        "notes": notes,
    }  # fmt: skip
    if complete and n_assets:
        out["recall_at_k"] = r3(recall_k_default)
        out["recall_at"] = {str(k): r3(v) for k, v in sorted(recall_at.items())}
        out["effort"] = {
            str(p): {"cells": effort[p]} if effort[p] is not None
            else {"cells": None, "reached": r3(final_share), "after": len(ranked)}
            for p in EFFORT_AT
        }  # fmt: skip
    else:
        out["recall_at_k"], out["recall_at"], out["effort"] = None, None, None
        if not complete:
            notes.append("reference is incomplete: recall@k and review effort are undefined; "
                         "AUROC and AP negatives may include unrecorded assets")  # fmt: skip
    return out


def score(
    ref: Reference, claims: list[tuple[float, float]], chips: list[Candidate] | None = None
) -> dict[str, Any]:
    """Score located claims (lat, lon) against a reference with the benchmark's unit and matching rule. With
    `chips` (the run's LGND results, first-seen order), also rank claims and chips (docs/ranking-metrics)."""
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
        **({"ranking": _ranking(ref, grid, occupied, asset_area_cells, area_cells, claims, chips)}
           if chips is not None else {}),
    }  # fmt: skip


def _ranking(
    ref: Reference,
    grid: Grid,
    occupied: dict[str, frozenset[Cell]],
    positives: set[Cell],
    area_cells: int,
    claims: list[tuple[float, float]],
    chips: list[Candidate],
) -> dict[str, Any]:
    cell_assets: dict[Cell, set[str]] = {}
    for rid, cells in occupied.items():
        for c in cells:
            cell_assets.setdefault(c, set()).add(rid)
    ranked = rank_cells(grid, ref.area, claims, chips)
    return ranking_metrics(ranked, cell_assets, len(occupied), positives, area_cells, ref.complete)


# ---- A run's reference: the snapshot in its own archive (design: The tie) ----

SNAPSHOT = "reference"


def from_run(
    run: Any,
    claims: list[tuple[float, float]],
    claims_block_missing: bool = False,
    repo_sha: str | None = None,
    chips: list[Candidate] | None = None,
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
        **score(ref, claims, chips),
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
