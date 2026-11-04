"""Display imagery for a chip's footprint, by LGND index. Presentation only; nothing here reaches the agent.

- naip: USGS The National Map NAIP ImageServer (US only), public.
- s2: EOX Sentinel-2 cloudless WMS (worldwide), public, CC BY-NC-SA 4.0; attribution: "Sentinel-2 cloudless -
  https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data)".
"""

from __future__ import annotations

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
