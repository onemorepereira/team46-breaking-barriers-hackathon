"""City-limits ground truth: official boundaries from US Census TIGERweb, and point-in-polygon checks.

TIGERweb `Places_CouSub_ConCity_SubMCD/MapServer/4` (Incorporated Places), queried by BASENAME and state
FIPS code, returns GeoJSON in WGS84. Standard library only.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TIGER_PLACES = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/4/query"
USER_AGENT = "team46-eval-harness/0.1"
STATE_FIPS = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
    "PR": "72",
}


class BoundaryError(Exception):
    pass


def parse_city(text: str) -> tuple[str, str]:
    """'Richardson, TX' -> ('Richardson', 'TX')."""
    m = re.match(r"^\s*(.+?)\s*,\s*([A-Za-z]{2})\s*$", text or "")
    if not m or m.group(2).upper() not in STATE_FIPS:
        raise BoundaryError(f"Write the city as 'City, ST' (for example 'Richardson, TX'), not {text!r}.")
    return m.group(1), m.group(2).upper()


def fetch_boundary(city: str, state: str, cache_dir: Path) -> dict[str, Any]:
    """The incorporated-place boundary as a GeoJSON Feature (cached on disk)."""
    cache = cache_dir / f"{state}-{re.sub(r'[^A-Za-z0-9]+', '_', city).lower()}.geojson"
    if cache.is_file():
        cached: dict[str, Any] = json.loads(cache.read_text(encoding="utf-8"))
        return cached
    safe_city = city.replace("'", "''")
    query = urllib.parse.urlencode(
        {
            "where": f"BASENAME='{safe_city}' AND STATE='{STATE_FIPS[state]}'",
            "outFields": "NAME,BASENAME,STATE,GEOID",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    req = urllib.request.Request(f"{TIGER_PLACES}?{query}", headers={"user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https endpoint
        data = json.loads(resp.read())
    features = data.get("features") or []
    if not features:
        raise BoundaryError(f"No incorporated place named {city!r} in {state} in Census TIGERweb.")
    feature: dict[str, Any] = features[0]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(feature), encoding="utf-8")
    return feature


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def contains(geometry: dict[str, Any], lon: float, lat: float) -> bool:
    """Point in Polygon/MultiPolygon; the first ring is the outline, the rest are holes."""
    polys = geometry["coordinates"] if geometry.get("type") == "MultiPolygon" else [geometry["coordinates"]]
    for rings in polys:
        if rings and _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, h) for h in rings[1:]):
            return True
    return False


def coordinate_pair(value: str) -> tuple[float, float] | None:
    """A claim value like '32.965, -96.7121' -> (lat, lon), or None."""
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", value or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None
