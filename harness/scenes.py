"""The scene a search result came from: the source image of the date and place LGND matched.

LGND returns, per result chip, its index (`s2` or `naip`), its observation date and its footprint, but no
image.
A basemap mosaic (EOX's 2023 Sentinel-2 cloudless, USGS's latest NAIP) shows the place on another date. This
module finds the observed scene in a public STAC catalogue and reads only the chip's pixels from its
Cloud-Optimized GeoTIFF (docs/observed-scenes):

- s2: Sentinel-2 L2A true-colour (`visual`, 10 m) via Element84 Earth Search (AWS open data, no key).
- naip: NAIP RGB(N) via Microsoft Planetary Computer, with its anonymous read token.

Shown in the console, and read by the visual check (harness/sharp.py, docs/visual-check); nothing here reaches
the agent.
"""

from __future__ import annotations

import io
import json
import re
import threading
import time
import urllib.request
from functools import lru_cache
from typing import Any

from harness.tiles import USER_AGENT, TileUnavailable  # tiles imports this module lazily (no cycle)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIMEOUT_S = 30
CATALOGUES = {
    # index: (STAC search endpoint, collection, RGB asset)
    "s2": ("https://earth-search.aws.element84.com/v1/search", "sentinel-2-l2a", "visual"),
    "naip": ("https://planetarycomputer.microsoft.com/api/stac/v1/search", "naip", "image"),
}
PC_TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/naip"
LABELS = {
    "s2": "Sentinel-2 L2A scene observed {date} (Copernicus Sentinel data, via Element84 Earth Search)",
    "naip": "NAIP scene observed {date} (USDA, via Microsoft Planetary Computer)",
}
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",  # don't list the bucket; open the one file
    "GDAL_HTTP_TIMEOUT": str(TIMEOUT_S),
    "GDAL_HTTP_MULTIPLEX": "YES",
    "VSI_CACHE": "TRUE",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
}


def label(index: str | None, observed: str | None) -> str | None:
    """The credit for an observed scene, or None when there is no date to look one up by."""
    if index not in LABELS or not observed or not DATE_RE.match(observed):
        return None
    return LABELS[index].format(date=observed)


def _post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https catalogues
        data: dict[str, Any] = json.loads(resp.read())
    return data


@lru_cache(maxsize=2048)
def find(index: str, bbox: tuple[float, ...], observed: str) -> str | None:
    """The RGB asset of the scene observed on that day that covers the chip (the least cloudy if several)."""
    endpoint, collection, asset = CATALOGUES[index]
    found = (
        _post_json(
            endpoint,
            {
                "collections": [collection],
                "bbox": list(bbox),
                "datetime": f"{observed}T00:00:00Z/{observed}T23:59:59Z",
                "limit": 10,
            },
        ).get("features")
        or []
    )
    w, s, e, n = bbox

    def covers(f: dict[str, Any]) -> bool:
        b = f.get("bbox") or []
        return len(b) >= 4 and b[0] <= w and b[1] <= s and b[2] >= e and b[3] >= n

    usable = [f for f in found if asset in (f.get("assets") or {})]
    usable.sort(key=lambda f: (not covers(f), (f.get("properties") or {}).get("eo:cloud_cover") or 0))
    return usable[0]["assets"][asset]["href"] if usable else None


_token: dict[str, Any] = {"value": None, "until": 0.0}
_token_lock = threading.Lock()


def _signed(index: str, href: str) -> str:
    """Planetary Computer blobs need its anonymous SAS token (refreshed a minute before it expires)."""
    if index != "naip":
        return href
    with _token_lock:
        if not _token["value"] or time.time() > _token["until"]:
            req = urllib.request.Request(PC_TOKEN_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https endpoint
                data = json.loads(resp.read())
            _token["value"] = data["token"]
            _token["until"] = time.time() + 50 * 60  # tokens last about an hour
        return f"{href}?{_token['value']}"


def render(href: str, bbox: tuple[float, ...], size: int = 384, min_coverage: float = 0.0) -> bytes:
    """Read the chip's window from a COG (RGB bands), keeping its proportions, as a JPEG.

    min_coverage: the share of pixels that must hold data (any non-zero band); below it, TileUnavailable.
    A catalogue footprint can be looser than the image's data (an OpenAerialMap mosaic whose bbox covered a
    point held data in 21% of its extent), so a caller that needs the place itself asks for most of it."""
    import numpy as np
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        window = from_bounds(*transform_bounds("EPSG:4326", src.crs, *bbox), transform=src.transform)
        ratio = float(window.height) / float(window.width) if window.width else 1.0
        w, h = (size, max(1, round(size * ratio))) if ratio <= 1 else (max(1, round(size / ratio)), size)
        data = src.read(
            [1, 2, 3], window=window, out_shape=(3, h, w), resampling=Resampling.bilinear,
            boundless=True, fill_value=0,
        )  # fmt: skip
    if not data.any():
        raise TileUnavailable("the scene has no data over this footprint")
    if min_coverage and float(data.any(axis=0).mean()) < min_coverage:
        raise TileUnavailable("the scene has data over only part of this footprint")
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(data.transpose(1, 2, 0)).astype("uint8")).save(
        buf, "JPEG", quality=88
    )
    return buf.getvalue()


def scene_jpeg(index: str, bbox: list[float], observed: str) -> bytes:
    """The observed scene under a chip, or TileUnavailable (no such scene, catalogue or storage down)."""
    if index not in CATALOGUES or not DATE_RE.match(observed or ""):
        raise TileUnavailable("no observation date to find the scene by")
    key = tuple(round(float(v), 6) for v in bbox)
    try:
        href = find(index, key, observed)
    except Exception as e:  # noqa: BLE001 - catalogue down or slow
        raise TileUnavailable(f"scene catalogue: {e}") from e
    if not href:
        raise TileUnavailable(f"no {index} scene observed {observed} covers this footprint")
    try:
        return render(_signed(index, href), key)
    except TileUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 - storage unreachable, bad window
        raise TileUnavailable(f"scene read: {e}") from e
