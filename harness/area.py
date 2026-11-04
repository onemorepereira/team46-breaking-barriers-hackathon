"""Search-area ground truth, taken from the prompt itself.

1. `extract_area(prompt)` asks a Bedrock model to pull out the area the prompt asks about (a city, a postal or
   ZIP code, a region, a country, an address, or a point plus radius) as structured JSON. Nothing is typed
   separately.
2. `resolve_area(spec)` turns that into an official boundary:
   - US ZIP codes: US Census TIGERweb 2020 ZIP Code Tabulation Areas (polygon).
   - Everything else: OpenStreetMap Nominatim (boundary polygons for cities, regions, countries and some
     postal codes, worldwide). Usage policy: a named User-Agent, at most 1 request per second, cached results.
   - Point plus radius: a circle polygon around the geocoded point.
   - A result that is only a point with no radius has no boundary, so the inside/outside check is skipped.
3. Geometry math lives in core.geometry; LGND's polygon format in tools.lgnd.areas.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core import geometry, prompts
from tools.lgnd.areas import to_lgnd_area

USER_AGENT = "team46-eval-harness/0.1 (hackathon evaluation tool)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
TIGER_ZCTA = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1/query"
)
KINDS = ("city", "postal_code", "region", "country", "address", "point_radius", "none")


class AreaError(Exception):
    pass


@dataclass
class AreaSpec:
    kind: str
    query: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    radius_km: float | None = None
    label: str | None = None


@dataclass
class Area:
    label: str
    kind: str
    source: str
    geometry: dict[str, Any] | None  # Polygon/MultiPolygon in lon/lat, or None when no boundary exists
    center: tuple[float, float] | None  # (lat, lon)
    note: str = ""

    def as_event(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = "area"
        return d


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()[:20]}.json"


def _cached(cache_dir: Path, key: str) -> Any:
    p = _cache_path(cache_dir, key)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _store(cache_dir: Path, key: str, value: Any) -> Any:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_dir, key).write_text(json.dumps(value), encoding="utf-8")
    return value


def extract_area(prompt: str, model_id: str, region: str, client: Any = None) -> AreaSpec:
    if client is None:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-runtime", region_name=region, config=Config(connect_timeout=10, read_timeout=60)
        )
    resp = client.converse(
        modelId=model_id,
        system=[{"text": prompts.load("harness/area_extract")}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 400},
    )
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise AreaError("couldn't read the search area from the prompt")
    data = json.loads(m.group(0))
    kind = data.get("kind") if data.get("kind") in KINDS else "none"
    radius = data.get("radius_km")
    return AreaSpec(
        kind=kind,
        query=data.get("query") or None,
        postal_code=(str(data["postal_code"]).strip() if data.get("postal_code") else None),
        country_code=(str(data["country_code"]).lower() if data.get("country_code") else None),
        radius_km=float(radius) if isinstance(radius, int | float) and radius > 0 else None,
        label=data.get("label") or data.get("query"),
    )


_nominatim_lock = threading.Lock()
_last_nominatim = 0.0


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https endpoints
        return json.loads(resp.read())


def _nominatim(params: dict[str, str], cache_dir: Path) -> list[dict[str, Any]]:
    global _last_nominatim
    params = {**params, "format": "jsonv2", "polygon_geojson": "1", "limit": "1"}
    key = "nominatim:" + json.dumps(params, sort_keys=True)
    hit = _cached(cache_dir, key)
    if hit is not None:
        return list(hit)
    with _nominatim_lock:  # usage policy: at most 1 request per second
        wait = 1.0 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            time.sleep(wait)
        result = _get_json(f"{NOMINATIM}?{urllib.parse.urlencode(params)}")
        _last_nominatim = time.monotonic()
    if not result:
        return []  # never cache a miss: it may be transient, and a cached [] would stick forever
    return list(_store(cache_dir, key, result))


ADMIN_WORDS = r"\b(province|prefecture|district|county|state|region|city|municipality|city limits|limits)\b"


def _candidates(spec: AreaSpec) -> list[dict[str, str]]:
    """Queries to try in order until one finds the place (romanizations and admin words vary)."""
    cc = {"countrycodes": spec.country_code} if spec.country_code else {}
    out: list[dict[str, str]] = []
    if spec.kind == "postal_code" and spec.postal_code:
        out.append({"postalcode": spec.postal_code, **cc})
    if spec.query:
        out.append({"q": spec.query, **cc})
        if cc:
            out.append({"q": spec.query})
        parts = [p.strip() for p in spec.query.split(",") if p.strip()]
        bare = re.sub(ADMIN_WORDS, "", parts[0], flags=re.I).strip() if parts else ""
        if bare and bare != parts[0]:
            out.append({"q": ", ".join([bare, *parts[1:]]), **cc})
        if bare and len(parts) > 1:
            field = "state" if spec.kind == "region" else "city"
            out.append({field: bare, "country": parts[-1]})
    unique: list[dict[str, str]] = []
    for c in out:
        if c not in unique:
            unique.append(c)
    return unique


def _zcta(zip5: str, cache_dir: Path) -> dict[str, Any] | None:
    key = f"zcta:{zip5}"
    hit = _cached(cache_dir, key)
    if hit is None:
        query = urllib.parse.urlencode(
            {
                "where": f"ZCTA5='{zip5}'",
                "outFields": "ZCTA5",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            }
        )
        hit = _store(cache_dir, key, _get_json(f"{TIGER_ZCTA}?{query}"))
    features = hit.get("features") or []
    geom: dict[str, Any] | None = features[0]["geometry"] if features else None
    return geom


def _polygonal(geojson: Any) -> dict[str, Any] | None:
    if isinstance(geojson, dict) and geojson.get("type") in ("Polygon", "MultiPolygon"):
        return geojson
    return None


def resolve_area(spec: AreaSpec, cache_dir: Path) -> Area | None:
    if spec.kind == "none" or not (spec.query or spec.postal_code):
        return None
    label = spec.label or spec.query or spec.postal_code or ""
    if spec.kind == "postal_code" and spec.postal_code:
        zip5 = spec.postal_code[:5]
        if spec.country_code in (None, "us") and re.fullmatch(r"\d{5}", zip5):
            geom = _zcta(zip5, cache_dir)
            if geom:
                return Area(label, "postal_code", "US Census TIGERweb, 2020 ZCTA", geom, None)
    hits: list[dict[str, Any]] = []
    for params in _candidates(spec):
        hits = _nominatim(params, cache_dir)
        if hits:
            break
    if not hits:
        raise AreaError(f"No location found for {label!r}.")
    hit = hits[0]
    center = (float(hit["lat"]), float(hit["lon"]))
    source = "OpenStreetMap Nominatim" + (f", {hit['osm_type']} {hit['osm_id']}" if hit.get("osm_id") else "")
    if spec.kind == "point_radius" and spec.radius_km:
        geom = geometry.circle(center[0], center[1], spec.radius_km)
        return Area(label, "point_radius", f"{source}, {spec.radius_km:g} km circle", geom, center)
    polygon = _polygonal(hit.get("geojson"))
    if polygon:
        return Area(label, spec.kind, source, polygon, center)
    note = "This location resolves to a point, not a boundary, so the inside/outside check is skipped."
    return Area(label, spec.kind, source, None, center, note=note)


def area_for_prompt(cfg: Any, prompt: str) -> tuple[Area | None, dict[str, Any]]:
    """Read the prompt's search area and resolve its boundary. Never raises: on failure the run goes ahead
    without an area, and the event says why."""
    try:
        model_key = cfg.get("narrative_model") or next(iter(cfg["models"]))
        spec = extract_area(prompt, cfg["models"][model_key]["id"], cfg["region"])
        area = resolve_area(spec, Path(cfg["out_dir"]) / "geo-cache")
        if area is None:
            return None, {
                "type": "area",
                "label": None,
                "note": "The prompt names no place, so there is no area check.",
            }
        return area, area.as_event()
    except Exception as e:  # noqa: BLE001 - reported, never fatal
        return None, {"type": "area", "label": None, "note": f"Couldn't resolve the prompt's area: {e}"}


def payload_area(area: Area | None, mode: str) -> dict[str, Any] | None:
    """What the agent receives: the label, the source, and LGND's polygon scope when there is a boundary."""
    if area is None or mode == "off":
        return None
    return {
        "label": area.label,
        "source": area.source,
        "mode": mode,
        "lgnd_area": to_lgnd_area(area.geometry) if area.geometry else None,
        "geometry": area.geometry,
    }
