"""The sharpest open image of a place, worldwide (docs/visual-check).

Sources, in the order the visual check tries them by default:

- vantor: Vantor (formerly Maxar) Open Data, about 0.3-0.5 m, disaster events only. A static STAC catalogue in
  `s3://vantor-opendata/events/`; each item's `visual` asset is an RGB COG. CC BY-NC 4.0.
- oam: OpenAerialMap, community and drone imagery (centimetres to metres). `api.openaerialmap.org/meta`; each
  result's `uuid` is a COG. Each item's own `license`, or CC BY 4.0 (OAM's terms) when it has none.
- naip: the most recent NAIP image (0.6-1 m, contiguous US) via Microsoft Planetary Computer.
- s2: a Sentinel-2 L2A scene (10 m, global) via Element84 Earth Search: the observed one, else the least
  cloudy of the last 90 days.

Network I/O only; no model calls. `candidates` yields what each catalogue lists; `read` returns the window as
a JPEG, or raises TileUnavailable so the caller moves on to the next candidate.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from harness import scenes
from harness.tiles import USER_AGENT, TileUnavailable

SOURCES = ("vantor", "oam", "naip", "s2")
TIMEOUT_S = 30
CACHE_S = 3600
PER_SOURCE = 3  # candidates tried per source and site
MIN_COVERAGE = 0.9
S2_DAYS = 90
VANTOR_HOST = "vantor-opendata.s3.amazonaws.com"
VANTOR_ROOT = f"https://{VANTOR_HOST}/events/catalog.json"
OAM_META = "https://api.openaerialmap.org/meta"
NAIP_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
S2_SEARCH = "https://earth-search.aws.element84.com/v1/search"
# GDAL opens only these hosts: image URLs come from third-party catalogue JSON.
ALLOWED_HOSTS = (
    "vantor-opendata.s3.amazonaws.com",
    "oin-hotosm-temp.s3.amazonaws.com",
    "oin-hotosm-temp.s3.us-east-1.amazonaws.com",
    "naipeuwest.blob.core.windows.net",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
)
LICENCES = {
    "vantor": "CC BY-NC 4.0",
    "oam": "CC BY 4.0",
    "naip": "Public Domain",
    "s2": "Copernicus Sentinel data, free and open",
}
CREDITS = {
    "vantor": "Vantor Open Data",
    "oam": "OpenAerialMap",
    "naip": "USDA NAIP, via Microsoft Planetary Computer",
    "s2": "Copernicus Sentinel-2, via Element84 Earth Search",
}


@dataclass(frozen=True)
class Image:
    source: str
    href: str
    gsd_m: float
    date: str | None
    licence: str
    credit: str


def allowed(href: str) -> bool:
    u = urllib.parse.urlparse(href)
    return u.scheme == "https" and u.hostname in ALLOWED_HOSTS


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https catalogues
        return json.loads(resp.read())


_cache: dict[str, tuple[float, Any]] = {}


def _cached(url: str) -> Any:
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    data = _get_json(url)
    _cache[url] = (time.time(), data)
    return data


def _ring_contains(ring: list[Any], lon: float, lat: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=False):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def covers(geometry: dict[str, Any] | None, lon: float, lat: float) -> bool:
    """Point in a GeoJSON Polygon or MultiPolygon (outer rings; holes ignored)."""
    if not isinstance(geometry, dict):
        return False
    coords = geometry.get("coordinates") or []
    polys = (
        [coords]
        if geometry.get("type") == "Polygon"
        else coords
        if geometry.get("type") == "MultiPolygon"
        else []
    )
    return any(p and _ring_contains([tuple(c[:2]) for c in p[0]], lon, lat) for p in polys)


def _in_bbox(b: list[float] | None, lon: float, lat: float) -> bool:
    return b is not None and len(b) >= 4 and b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def _vantor_url(base: str, href: str) -> str:
    """A catalogue link, resolved and kept on the Vantor host: the catalogue is third-party JSON."""
    url = urllib.parse.urljoin(base, href)
    if urllib.parse.urlparse(url).scheme != "https" or urllib.parse.urlparse(url).hostname != VANTOR_HOST:
        raise ValueError(f"catalogue link off the Vantor host: {url[:80]}")
    return url


def _vantor(lat: float, lon: float) -> list[Image]:
    root = _cached(VANTOR_ROOT)
    found: list[tuple[str, Image]] = []
    for link in root.get("links") or []:
        if link.get("rel") != "child":
            continue
        coll_url = _vantor_url(VANTOR_ROOT, link["href"])
        coll = _cached(coll_url)
        boxes = ((coll.get("extent") or {}).get("spatial") or {}).get("bbox") or []
        if not any(_in_bbox(b, lon, lat) for b in boxes):
            continue
        for item_link in coll.get("links") or []:
            if item_link.get("rel") != "item":
                continue
            item = _cached(_vantor_url(coll_url, item_link["href"]))
            if not _in_bbox(item.get("bbox"), lon, lat) or not covers(item.get("geometry"), lon, lat):
                continue
            href = ((item.get("assets") or {}).get("visual") or {}).get("href")
            props = item.get("properties") or {}
            when = str(props.get("datetime") or "")
            if href:
                gsd = props.get("pan_gsd") or props.get("gsd") or 0.5
                found.append(
                    (
                        when,
                        Image(
                            "vantor",
                            href,
                            float(gsd),
                            when[:10] or None,
                            LICENCES["vantor"],
                            CREDITS["vantor"],
                        ),
                    )
                )
    found.sort(key=lambda t: t[0], reverse=True)
    return [img for _, img in found]


def _oam(lat: float, lon: float) -> list[Image]:
    d = 1e-5
    q = urllib.parse.urlencode({"bbox": f"{lon - d},{lat - d},{lon + d},{lat + d}", "limit": 20})
    results = (_get_json(f"{OAM_META}?{q}") or {}).get("results") or []
    hits = [r for r in results if r.get("uuid") and covers(r.get("geojson"), lon, lat)]
    hits.sort(key=lambda r: (str(r.get("acquisition_end") or ""), -float(r.get("gsd") or 99)), reverse=True)
    return [
        Image(
            "oam",
            r["uuid"],
            float(r.get("gsd") or 0),
            str(r.get("acquisition_end") or "")[:10] or None,
            str(r.get("license") or LICENCES["oam"]),
            f"{CREDITS['oam']}" + (f" ({r['provider']})" if r.get("provider") else ""),
        )
        for r in hits
    ]


def _stac(url: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    return list(scenes._post_json(url, body).get("features") or [])


def _naip(lat: float, lon: float) -> list[Image]:
    feats = _stac(
        NAIP_SEARCH,
        {
            "collections": ["naip"],
            "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
            "limit": 2,
        },
    )
    out = []
    for f in feats:
        href = ((f.get("assets") or {}).get("image") or {}).get("href")
        p = f.get("properties") or {}
        if href:
            out.append(
                Image(
                    "naip",
                    href,
                    float(p.get("gsd") or 0.6),
                    str(p.get("datetime") or "")[:10] or None,
                    LICENCES["naip"],
                    CREDITS["naip"],
                )
            )
    return out


def _s2(
    lat: float, lon: float, bbox: tuple[float, ...], observed: str | None, index: str | None
) -> list[Image]:
    out = []
    if index == "s2" and observed and scenes.DATE_RE.match(observed):
        href = scenes.find("s2", bbox, observed)
        if href:
            out.append(Image("s2", href, 10.0, observed, LICENCES["s2"], CREDITS["s2"]))
    if not out:
        end = datetime.now(UTC)
        feats = _stac(
            S2_SEARCH,
            {
                "collections": ["sentinel-2-l2a"],
                "intersects": {"type": "Point", "coordinates": [lon, lat]},
                "datetime": f"{(end - timedelta(days=S2_DAYS)):%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}",
                "query": {"eo:cloud_cover": {"lt": 20}},
                "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                "limit": 1,
            },
        )
        for f in feats:
            href = ((f.get("assets") or {}).get("visual") or {}).get("href")
            if href:
                when = str((f.get("properties") or {}).get("datetime") or "")[:10] or None
                out.append(Image("s2", href, 10.0, when, LICENCES["s2"], CREDITS["s2"]))
    return out


def candidates(
    lat: float,
    lon: float,
    bbox: tuple[float, ...],
    *,
    observed: str | None = None,
    index: str | None = None,
    sources: tuple[str, ...] | list[str] = SOURCES,
    tried: list[str] | None = None,
) -> Iterator[Image]:
    """Images covering the point, source by source in `sources` order. A catalogue that fails is skipped;
    `tried` (if given) gets one "<source>:<n found|none|error ...>" entry per source asked."""
    for source in sources:
        try:
            if source == "vantor":
                found = _vantor(lat, lon)
            elif source == "oam":
                found = _oam(lat, lon)
            elif source == "naip":
                found = _naip(lat, lon)
            elif source == "s2":
                found = _s2(lat, lon, bbox, observed, index)
            else:
                continue
        except Exception as e:  # noqa: BLE001 - a catalogue down or slow: try the next source
            if tried is not None:
                tried.append(f"{source}:error {type(e).__name__}")
            continue
        found = [img for img in found if allowed(img.href)][:PER_SOURCE]
        if tried is not None:
            tried.append(f"{source}:{len(found) or 'none'}")
        yield from found


def read(img: Image, bbox: tuple[float, ...], size: int = 768) -> bytes:
    """The image's window over bbox as a JPEG, or TileUnavailable (no data there, storage unreachable)."""
    if not allowed(img.href):
        raise TileUnavailable("image host not allowed")
    href = scenes._signed("naip", img.href) if img.source == "naip" else img.href
    try:
        return scenes.render(href, bbox, size=size, min_coverage=MIN_COVERAGE)
    except TileUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 - storage unreachable, bad window
        raise TileUnavailable(f"image read: {e}") from e
