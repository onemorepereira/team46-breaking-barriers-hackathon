"""Display imagery for a chip's footprint, by LGND index. Presentation only; nothing here reaches the agent.

- naip: USGS The National Map NAIP ImageServer (US only), public.
- s2: EOX Sentinel-2 cloudless WMS (worldwide), public, CC BY-NC-SA 4.0; attribution: "Sentinel-2 cloudless -
  https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data)".
"""

from __future__ import annotations

import hashlib
import math
from urllib.parse import urlencode

NAIP = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage"
S2 = "https://tiles.maps.eox.at/wms"
ATTRIBUTION = {
    "naip": "USGS The National Map, NAIP",
    "s2": "Sentinel-2 cloudless by EOX (contains modified Copernicus Sentinel data)",
}


def tile_url(index: str | None, bbox: list[float], size: int = 384) -> str:
    box = ",".join(str(float(v)) for v in bbox)
    if index == "naip":
        q = {
            "bbox": box,
            "bboxSR": 4326,
            "imageSR": 3857,
            "size": f"{size},{size}",
            "format": "jpg",
            "f": "image",
        }
        return f"{NAIP}?{urlencode(q)}"
    q = {
        "service": "WMS",
        "request": "GetMap",
        "version": "1.1.1",
        "layers": "s2cloudless-2023",
        "styles": "",
        "srs": "EPSG:4326",
        "bbox": box,
        "width": size,
        "height": size,
        "format": "image/jpeg",
    }
    return f"{S2}?{urlencode(q)}"


# ---------- the console's own tile endpoints (harness/tiles.py serves them; docs/tile-cache) ----------
# Imagery basemaps the console caches on its server. OpenStreetMap is deliberately absent: its tile policy
# discourages caching proxies and forbids offline use, so the browser fetches it directly.
BASE_MAXZOOM = {"s2": 15, "usgs": 16, "naip": 19}
CHIP_INDEXES = ("naip", "s2")
MAX_CHIP_DEG = 2.0  # a result tile is a footprint; anything wider is refused (user's call, 2026-11-04)
_R = 6378137.0  # Web Mercator sphere radius, m


def base_url(source: str, z: int, x: int, y: int) -> str:
    """The upstream URL of one 256 px basemap tile (XYZ scheme). Callers validate with valid_xyz first."""
    if source == "s2":
        return f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g/{z}/{y}/{x}.jpg"
    if source == "usgs":
        return (
            f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"
        )
    if source == "naip":
        size = 2 * math.pi * _R / 2**z
        minx, maxy = -math.pi * _R + x * size, math.pi * _R - y * size
        box = f"{minx},{maxy - size},{minx + size},{maxy}"
        q = {"bbox": box, "bboxSR": 3857, "imageSR": 3857, "size": "256,256", "format": "jpg", "f": "image"}
        return f"{NAIP}?{urlencode(q)}"
    raise ValueError(f"unknown basemap source {source!r}")


def valid_xyz(source: str, z: int, x: int, y: int) -> bool:
    top = BASE_MAXZOOM.get(source)
    return top is not None and 0 <= z <= top and 0 <= x < 2**z and 0 <= y < 2**z


def parse_bbox(text: str) -> list[float] | None:
    """`w,s,e,n` in degrees, finite, ordered, inside Web Mercator's range and at most MAX_CHIP_DEG a side."""
    parts = text.split(",")
    if len(parts) != 4:
        return None
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError:
        return None
    if not all(math.isfinite(v) for v in (w, s, e, n)):
        return None
    if not (-180 <= w < e <= 180 and -85.06 <= s < n <= 85.06):
        return None
    if e - w > MAX_CHIP_DEG or n - s > MAX_CHIP_DEG:
        return None
    return [w, s, e, n]


def bbox_text(bbox: list[float]) -> str:
    return ",".join(f"{float(v):.6f}" for v in bbox)


def chip_key(index: str, bbox: list[float]) -> str:
    """The file name of a result tile in the disk cache and the archive."""
    return hashlib.sha1(f"{index}|{bbox_text(bbox)}|384".encode(), usedforsecurity=False).hexdigest()[:20]


RUN_ID_RE = r"^[A-Za-z0-9-]{1,64}$"  # the shape of a run ID (a UUID, or a test's run-0001)


def console_chip_url(index: str | None, bbox: list[float], run_id: str | None = None) -> str:
    """Where the console page loads a result tile: our endpoint. A bbox the endpoint would refuse (wider than
    MAX_CHIP_DEG, or outside Web Mercator) keeps its provider URL, so it still shows, uncached."""
    if parse_bbox(bbox_text(bbox)) is None:
        return tile_url(index, bbox)
    idx = index if index in CHIP_INDEXES else "s2"
    url = f"/tiles/chip/{idx}/{bbox_text(bbox)}.jpg"
    return f"{url}?run={run_id}" if run_id else url
