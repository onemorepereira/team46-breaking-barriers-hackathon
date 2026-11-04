"""Measured criteria, trace integrity and fatal gates: computed by code from the archive (spec AC2, AC6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from analysis import check, provenance
from analysis.provenance import FENCE_RE, MATCHED, Provenance
from analysis.trace import Run
from core import geometry
from tools.lgnd import descriptors as lgnd
from tools.lgnd.results import _json, chips_of


@dataclass
class Located:
    """One located result: an LGND chip or a coordinate claim, and whether it's inside the area."""

    source: str  # "chip" | "claim"
    ref: str | None
    node: str | None
    lat: float
    lon: float
    inside: bool | None  # None when there's no area to test against
    bbox: list[float] | None = None
    index: str | None = None
    label: str | None = None
    similarity: float | None = None
    observed: str | None = None
    claim: str | None = None


@dataclass
class Measured:
    claims_total: int
    claims_matched: int
    claims_block_missing: bool
    claim_provenance: float | None  # 0..1, None = N/A
    area_label: str | None
    area_geometry: dict[str, Any] | None
    located: list[Located]
    claims_inside: int
    claims_located: int
    area_compliance: float | None  # coordinate claims inside / located; None = N/A
    chips_inside: int
    chips_total: int
    search_footprint: float | None  # LGND results inside; shown, not scored
    missing_fields: int
    archive_errors: int
    trace_integrity: bool
    gates: list[dict[str, str]] = field(default_factory=list)

    def score_of(self, criterion_id: str) -> float | None:
        return {"claim_provenance": self.claim_provenance, "area_compliance": self.area_compliance}.get(
            criterion_id
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def search_area(run: Run) -> dict[str, Any] | None:
    area = (run.manifest.get("snapshot") or {}).get("search_area")
    return area if isinstance(area, dict) else None


def located_results(run: Run, prov: Provenance, geom: dict[str, Any] | None) -> list[Located]:
    def inside(lat: float, lon: float) -> bool | None:
        return geometry.contains(geom, lon, lat) if geom else None

    out: list[Located] = []
    seen: set[str] = set()
    for span in run.tool_results:
        if span.attr("harness.tool.server") != lgnd.SERVER or span.attr("harness.tool.status") == "error":
            continue
        text = run.tool_result_text(span) or str(span.attr("harness.tool.result", ""))
        data = _json(text)
        for c in chips_of(data) if data else []:
            key = str(c.get("node") or c.get("chip_id") or f"{c['lat']},{c['lon']}")
            if key in seen:
                continue
            seen.add(key)
            lat, lon = float(c["lat"]), float(c["lon"])
            sim = c.get("similarity")
            out.append(
                Located(
                    "chip",
                    span.attr("harness.tool.ref"),
                    c.get("node"),
                    lat,
                    lon,
                    inside(lat, lon),
                    bbox=c.get("bbox"),
                    index=c.get("index"),
                    label=c.get("label"),
                    similarity=float(sim) if isinstance(sim, int | float) else None,
                    observed=c.get("observed"),
                )
            )
    for cl in prov.claims:
        pair = geometry.coordinate_pair(cl.value)
        if pair:
            out.append(
                Located("claim", cl.ref, None, pair[0], pair[1], inside(pair[0], pair[1]), claim=cl.claim)
            )
    return out


def answer_text(final_output: str) -> str:
    """The final answer without its fenced JSON blocks."""
    return FENCE_RE.sub("", final_output or "").strip()


def measure(run: Run, prov: Provenance | None = None) -> Measured:
    prov = prov or provenance.grade(run)
    counts = prov.counts()
    total = len(prov.claims)
    answer = answer_text(run.final_output)
    if prov.claims_block_missing:
        claim_share: float | None = 0.0
    elif total:
        claim_share = counts[MATCHED] / total
    else:
        claim_share = 0.0 if answer else None  # prose with no declared claims is not grounded
    area = search_area(run)
    geom = area.get("geometry") if area else None
    located = located_results(run, prov, geom if isinstance(geom, dict) else None)
    claims_t = [x for x in located if x.source == "claim" and x.inside is not None]
    chips_t = [x for x in located if x.source == "chip" and x.inside is not None]
    missing = len(check.check_run(run))
    archive_errors = int(run.manifest.get("archive_errors", 0) or 0)
    gates = []
    if not answer:
        gates.append({"id": "no_answer", "reason": "the run produced no final answer beyond a claims block"})
    if not any(s.attr("harness.tool.status") not in ("error", None) for s in run.tool_results):
        gates.append({"id": "no_tool_data", "reason": "no tool call succeeded"})
    return Measured(
        claims_total=total,
        claims_matched=counts[MATCHED],
        claims_block_missing=prov.claims_block_missing,
        claim_provenance=claim_share,
        area_label=(area or {}).get("label"),
        area_geometry=geom if isinstance(geom, dict) else None,
        located=located,
        claims_inside=sum(1 for x in claims_t if x.inside),
        claims_located=len(claims_t),
        area_compliance=sum(1 for x in claims_t if x.inside) / len(claims_t) if claims_t else None,
        chips_inside=sum(1 for x in chips_t if x.inside),
        chips_total=len(chips_t),
        search_footprint=sum(1 for x in chips_t if x.inside) / len(chips_t) if chips_t else None,
        missing_fields=missing,
        archive_errors=archive_errors,
        trace_integrity=missing == 0 and archive_errors == 0,
        gates=gates,
    )
