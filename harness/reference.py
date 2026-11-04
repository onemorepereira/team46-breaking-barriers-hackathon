"""Tie runs to reference sets, and build reference sets (docs/adb-alignment AC3, AC5).

Reference sets live in the repo under references/<id>/ (reference.json, features.geojson, BUILD.md). Tying a
run snapshots the set into the run's own archive (runs/<id>/reference/), and analysis.reference.from_run
scores from that snapshot, so replay reproduces it and a rebuilt set never changes an old run's metrics.
"""

from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analysis import reference as ref_mod
from core import geometry
from core.store import Store

REPO = Path(__file__).resolve().parents[1]
REFERENCES = REPO / "references"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")


def load(ref_id: str, root: Path | None = None) -> ref_mod.Reference:
    if not ID_RE.match(ref_id or ""):
        raise ref_mod.ReferenceError(f"invalid reference id {ref_id!r}")
    return ref_mod.load((root or REFERENCES) / ref_id)


def available(root: Path | None = None) -> list[str]:
    base = root or REFERENCES
    return sorted(p.name for p in base.iterdir() if (p / "reference.json").is_file()) if base.is_dir() else []


def repo_sha(ref_id: str | None, root: Path | None = None) -> str | None:
    """The repo set's current sha256, for the informational `stale` flag; None if it can't be loaded."""
    try:
        return load(str(ref_id), root).sha256
    except ref_mod.ReferenceError:
        return None


def tie(store: Store, run_id: str, ref_id: str, by: str, root: Path | None = None) -> dict[str, Any]:
    """Snapshot a reference set into the run's archive and record the tie (validates the set first)."""
    ref = load(ref_id, root)
    base = f"runs/{run_id}/{ref_mod.SNAPSHOT}"
    store.write_text(f"{base}/reference.json", json.dumps(ref.meta, indent=1))
    fc = {"type": "FeatureCollection", "features": ref.features}
    store.write_text(f"{base}/features.geojson", json.dumps(fc))
    rec = {
        "schema_version": 1,
        "id": ref.id,
        "sha256": ref.sha256,
        "tied_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by": by,
    }
    store.write_text(f"{base}/tie.json", json.dumps(rec, indent=1))
    return rec


# ---- Builder: USGS USPVDB solar facilities in one county, with the Census county boundary (AC5) ----

USPVDB_URL = "https://energy.usgs.gov/uspvdb/assets/data/uspvdbGeoJSON.zip"
TIGER_COUNTIES = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "team46-eval-harness reference builder"})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 - fixed https URLs
        return bytes(r.read())


def tiger_county(state_fips: str, county: str) -> dict[str, Any]:
    """The county's boundary from US Census TIGERweb (a US government work), as a GeoJSON Feature."""
    q = urllib.parse.urlencode(
        {
            "where": f"STATE='{int(state_fips):02d}' AND BASENAME='{county.replace(chr(39), chr(39) * 2)}'",
            "outFields": "NAME,GEOID,BASENAME,STATE",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    fc = json.loads(_get(f"{TIGER_COUNTIES}?{q}"))
    feats = fc.get("features") or []
    if len(feats) != 1:
        n = len(feats)
        raise ref_mod.ReferenceError(f"TIGERweb returned {n} counties for {county} (state {state_fips})")
    return dict(feats[0])


SIMPLIFY_DEG = 0.0005  # about 50 m: well under the 160 m cell, and keeps scoring fast on every view


def _simplified(geom: dict[str, Any]) -> dict[str, Any]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    out = [[geometry.simplify(ring, SIMPLIFY_DEG) for ring in poly] for poly in polys]
    return {"type": geom["type"], "coordinates": out if geom["type"] == "MultiPolygon" else out[0]}


def build_uspvdb(
    state: str,
    state_fips: str,
    county: str,
    ref_id: str,
    uspvdb_zip: bytes | None = None,
    county_feature: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Write references/<ref_id>/ from USPVDB: every facility in one county, inside its TIGER boundary."""
    if not ID_RE.match(ref_id):
        raise ref_mod.ReferenceError(f"invalid reference id {ref_id!r}")
    raw = uspvdb_zip if uspvdb_zip is not None else _get(USPVDB_URL)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        gj_name = next(n for n in z.namelist() if n.endswith(".geojson"))
        fc = json.loads(z.read(gj_name))
    version = re.search(r"v(\d+)_(\d+)_(\d{8})", gj_name)
    ver = f"{version.group(1)}.{version.group(2)}" if version else "unknown"
    dated = version.group(3) if version else "unknown"
    feats = [
        f
        for f in fc["features"]
        if (f.get("properties") or {}).get("p_state") == state and f["properties"].get("p_county") == county
    ]
    if not feats:
        raise ref_mod.ReferenceError(f"USPVDB has no facilities in {county}, {state}")
    cf = county_feature or tiger_county(state_fips, county)
    props = cf.get("properties") or {}
    keep = ("p_name", "p_cap_ac", "p_cap_dc", "p_year", "p_area", "eia_id", "p_img_date")
    out_feats = [
        {
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "ref_id": str(f["properties"].get("case_id")),
                **{k: f["properties"].get(k) for k in keep},
            },
        }
        for f in feats
    ]
    retrieved = datetime.now(UTC).strftime("%Y-%m-%d")
    meta: dict[str, Any] = {
        "schema_version": 1,
        "id": ref_id,
        "concept": "solar_farm",
        "place": f"{props.get('NAME') or county + ' County'}, {state}, US",
        "area": _simplified(cf["geometry"]),
        "area_source": f"US Census TIGERweb State_County/MapServer/1, GEOID {props.get('GEOID')}; "
        f"simplified to {SIMPLIFY_DEG} degrees (about 50 m)",
        "area_licence": "U.S. Census Bureau TIGER: a U.S. Government work "
        "(assumed public domain; no licence page found 2026-11-04)",
        "completeness": "complete",
        "completeness_note": f"Every facility USPVDB v{ver} lists for this county: ground-mounted PV of "
        "at least 1 MW from the EIA-860 base list, visible in high-resolution imagery. USGS notes that some "
        "facilities outside EIA-860 are not included.",
        "source": {
            "name": "USGS U.S. Large-Scale Solar Photovoltaic Database (USPVDB)",
            "url": USPVDB_URL,
            "version": f"{ver} ({dated})",
            "retrieved": retrieved,
            "boundary": "US Census TIGERweb counties",
        },
        "licence": {
            "id": "USPVDB-no-constraints",
            "name": "USPVDB (USGS and Berkeley Lab): access and use constraints None per its metadata",
            "url": "https://energy.usgs.gov/uspvdb/data/",
            "attribution": "Sources: USGS USPVDB; U.S. Census Bureau TIGER",
            "commercial_use_ok": True,
        },
        "unit": "asset",
        "cell_m": 160,
    }
    dest = (root or REFERENCES) / ref_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "reference.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    fc_out = {"type": "FeatureCollection", "features": out_feats}
    (dest / "features.geojson").write_text(json.dumps(fc_out) + "\n", encoding="utf-8")
    (dest / "BUILD.md").write_text(
        f"# {ref_id}\n\nBuilt on {retrieved} by:\n\n```sh\n"
        f"uv run harness reference build-uspvdb --state {state} "
        f"--state-fips {state_fips} --county {county} --id {ref_id}\n```\n\n"
        f"- **Facilities:** {len(out_feats)}, from {meta['source']['name']} v{ver} ({dated}), {USPVDB_URL}\n"
        f"- **Area:** {meta['area_source']}\n"
        f"- **Licence:** {meta['licence']['name']}\n"
        "- **Completeness:** see `completeness_note` in reference.json\n",
        encoding="utf-8",
    )
    ref = ref_mod.load(dest)  # validates what was written
    return {"id": ref.id, "assets": len(ref.features), "sha256": ref.sha256, "dir": str(dest)}
