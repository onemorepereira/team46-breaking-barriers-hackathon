"""Which data, boundaries, models and reference sets a run used, and under which licences (docs/adb-alignment
AC6).

Licence facts live in a sourced table (each entry cites where the fact comes from), so the list is computed
from the archive alone and replays offline. Anything we can't establish is listed as unknown: check before
sharing."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from analysis import signals
from analysis.trace import Run
from tools.lgnd import descriptors as lgnd


@dataclass(frozen=True)
class Source:
    name: str
    provider: str
    licence: str
    url: str
    attribution: str = ""
    commercial_use_ok: bool | None = None  # None: unknown
    presentable: bool | None = None  # may be shown to governments and third parties
    fact_source: str = ""  # where the licence fact comes from


UNKNOWN = "Unknown: check before sharing"

SOURCES: dict[str, Source] = {
    "lgnd:naip": Source(
        "NAIP aerial imagery (via LGND Geo)",
        "USDA Farm Production and Conservation Business Center",
        "Public Domain with Attribution",
        "https://registry.opendata.aws/naip/",
        "USDA NAIP imagery",
        True,
        True,
        "AWS Open Data registry, datasets/naip.yaml `License`",
    ),
    "lgnd:s2": Source(
        "Sentinel-2 imagery (via LGND Geo)",
        "European Space Agency / Copernicus",
        "Copernicus Sentinel data: free, full and open access",
        "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice",
        "Contains modified Copernicus Sentinel data [year]",
        True,
        True,
        "Sentinel Data Legal Notice (ESA); AWS Open Data registry, datasets/sentinel-2-l2a-cogs.yaml",
    ),
    "lgnd": Source(
        "LGND Geo service (search, classifiers, image checks)",
        "LGND AI, Inc.",
        UNKNOWN,
        lgnd.SERVICE_URL,
        "",
        None,
        None,
        "No public terms found (2026-11-04); ask LGND",
    ),
    "boundary:osm": Source(
        "OpenStreetMap boundary (via Nominatim)",
        "OpenStreetMap contributors",
        "ODbL 1.0",
        "https://www.openstreetmap.org/copyright",
        "© OpenStreetMap contributors",
        True,
        True,
        "openstreetmap.org/copyright",
    ),
    "boundary:census": Source(
        "US Census boundary (TIGERweb)",
        "U.S. Census Bureau",
        "U.S. Government work (assumed public domain)",
        "https://tigerweb.geo.census.gov/",
        "U.S. Census Bureau, TIGER/Line",
        True,
        True,
        "Assumption: U.S. federal work; no licence page found (2026-11-04)",
    ),
    "model": Source(
        "Amazon Bedrock model",
        "Amazon Web Services",
        "AWS Service Terms (Amazon Bedrock)",
        "https://aws.amazon.com/service-terms/",
        "",
        True,
        True,
        "AWS Service Terms",
    ),
}

LICENCE_RE = re.compile(r'"?licen[sc]e"?\s*[:=]\s*"?([^"\n]{2,200})', re.I)
OPEN_RE = re.compile(
    r"CC[- ]BY(?![- ](NC|ND))|CC0|public domain|ODbL|Open Data Commons|MIT|Apache|open", re.I
)
CLOSED_RE = re.compile(r"\b(NC|ND|non[- ]?commercial|academic|proprietary|restricted)\b", re.I)


def roda_licence(run: Run, dataset: str) -> str | None:
    """The registry `license` a RODA tool returned for this dataset, read from the archived tool results."""
    for s in run.tool_results:
        if s.attr("harness.tool.server") != "roda" or s.attr("harness.tool.status") == "error":
            continue
        args = s.json_attr("harness.tool.arguments", {}) or {}
        if not isinstance(args, dict) or dataset not in json.dumps(args):
            continue
        text = run.tool_result_text(s) or str(s.attr("harness.tool.result", ""))
        m = LICENCE_RE.search(text.replace('\\"', '"'))
        if m:
            return m.group(1).strip().rstrip(",").strip()
    return None


def _roda_source(dataset: str, lic: str | None) -> Source:
    if not lic:
        return Source(
            f"AWS Open Data: {dataset}",
            "AWS Open Data registry",
            UNKNOWN,
            f"https://registry.opendata.aws/{dataset}/",
            "",
            None,
            None,
            "No licence in the archived tool results",
        )
    ok = bool(OPEN_RE.search(lic)) and not CLOSED_RE.search(lic)
    return Source(
        f"AWS Open Data: {dataset}",
        "AWS Open Data registry",
        lic,
        f"https://registry.opendata.aws/{dataset}/",
        "",
        ok or None,
        ok or None,
        "The registry `License` field, as returned by the RODA tool",
    )


_VISUAL_SOURCES = {
    # source: (name, provider, url, fact source); the licence comes from each record (docs/visual-check)
    "vantor": ("Vantor Open Data imagery (visual check)", "Vantor (formerly Maxar)",
               "https://registry.opendata.aws/vantor-open-data/", "s3://vantor-opendata/LICENSE.TXT"),
    "oam": ("OpenAerialMap imagery (visual check)", "OpenAerialMap contributors (Open Imagery Network)",
            "https://openaerialmap.org/legal", "OpenAerialMap terms; the item's own `license` field"),
    "naip": ("NAIP aerial imagery (visual check)", "USDA Farm Production and Conservation Business Center",
             "https://planetarycomputer.microsoft.com/dataset/naip",
             "AWS Open Data registry, datasets/naip.yaml"),
    "s2": ("Sentinel-2 imagery (visual check)", "European Space Agency / Copernicus",
           "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice",
           "Sentinel Data Legal Notice (ESA)"),
}  # fmt: skip


def _commercial(licence: str) -> bool | None:
    """Commercial use allowed? NC licences: no; CC BY, public domain, Copernicus: yes; else unknown."""
    text = licence.upper()
    if "NC" in text.replace("-", " ").split() or "NON-COMMERCIAL" in text or "NONCOMMERCIAL" in text:
        return False
    if text.startswith(("CC BY", "CC-BY", "PUBLIC DOMAIN", "COPERNICUS")):
        return True
    return None


def _visual_items(run: Run) -> list[dict[str, Any]]:
    """One item per (source, licence) the run's visual check used, read from its archive (offline)."""
    from analysis.judging import visual

    pairs: dict[tuple[str, str], None] = {}
    for x in (visual.load(run) or {}).get("sites") or []:
        if isinstance(x, dict) and x.get("source") in _VISUAL_SOURCES and x.get("verdict") in VISUAL_USED:
            pairs[(str(x["source"]), str(x.get("licence") or UNKNOWN))] = None
    items = []
    for source, licence in pairs:
        name, provider, url, fact = _VISUAL_SOURCES[source]
        ok = _commercial(licence)
        # Presentable follows commercial use (the convention); an NC licence is "check before sharing".
        items.append(_item(Source(name, provider, licence, url, provider, ok, ok or None, fact),
                           "data", "visual check", f"visual:{source}:{licence}"))  # fmt: skip
    return items


def _visual_models(run: Run) -> list[str]:
    from analysis.judging import visual

    sites = (visual.load(run) or {}).get("sites") or []
    return list(dict.fromkeys(str(x["model"]) for x in sites if isinstance(x, dict) and x.get("model")))


VISUAL_USED = ("present", "absent", "unclear")


def _item(src: Source, role: str, used_as: str, key: str) -> dict[str, Any]:
    return {"key": key, "role": role, "used_as": used_as, **asdict(src)}


def for_run(
    run: Run,
    reference: dict[str, Any] | None = None,
    judges: list[str] | None = None,
    narrative_model: str | None = None,
) -> dict[str, Any]:
    """Every source the run relied on, its licence, and whether the result is presentable (AC6, AC7)."""
    items: list[dict[str, Any]] = []
    used_lgnd = any(s.attr("harness.tool.server") == lgnd.SERVER for s in run.tool_results)
    for d in signals.datasets_accessed(run):
        name = d["dataset"]
        if name in SOURCES:
            items.append(_item(SOURCES[name], "data", f"via {d['via']}", name))
        elif name.startswith(f"{lgnd.SERVER}:"):
            items.append(
                _item(
                    Source(
                        f"LGND index {name.split(':', 1)[1]}",
                        "LGND AI, Inc.",
                        UNKNOWN,
                        lgnd.SERVICE_URL,
                        "",
                        None,
                        None,
                        "Not in the licence table",
                    ),
                    "data",
                    f"via {d['via']}",
                    name,
                )
            )
        elif name.startswith("dataset unknown") and any(t in lgnd.TOOL_NAMES for t in d["via"].split(", ")):
            continue  # an LGND tool that names no index: covered by the LGND service entry below
        elif name.startswith("dataset unknown"):
            items.append(
                _item(
                    Source(name, "unknown", UNKNOWN, "", "", None, None, "Unmapped tool"),
                    "data",
                    f"via {d['via']}",
                    name,
                )
            )
        else:
            items.append(_item(_roda_source(name, roda_licence(run, name)), "data", f"via {d['via']}", name))
    if used_lgnd:
        items.append(_item(SOURCES["lgnd"], "service", "imagery search and checks", "lgnd"))
    items += _visual_items(run)
    area = (run.manifest.get("snapshot") or {}).get("search_area") or {}
    src = str(area.get("source") or "")
    if src:
        key = "boundary:census" if "census" in src.lower() or "tiger" in src.lower() else "boundary:osm"
        items.append(_item(SOURCES[key], "boundary", area.get("label") or "requested area", key))
    models = []
    if run.manifest.get("model_key"):
        models.append((str(run.manifest["model_key"]), "agent"))
    models += [(k, "judge") for k in judges or []]
    models += [(k, "visual check") for k in _visual_models(run)]
    if narrative_model:
        models.append((narrative_model, "narrative"))
    roles: dict[str, list[str]] = {}
    for key, role in models:
        roles.setdefault(key, []).append(role)
    for key, rs in roles.items():
        role = ", ".join(rs)
        m = SOURCES["model"]
        items.append(
            _item(
                Source(f"{key} ({m.name})", m.provider, m.licence, m.url, "", True, True, m.fact_source),
                "model",
                role,
                f"model:{key}",
            )
        )
    if reference:
        lic = reference.get("licence") or {}
        items.append(
            _item(
                Source(
                    f"Reference set {reference.get('id')}",
                    str((reference.get("source") or {}).get("name", "")),
                    str(lic.get("name") or UNKNOWN),
                    str(lic.get("url") or ""),
                    str(lic.get("attribution") or ""),
                    lic.get("commercial_use_ok"),
                    lic.get("commercial_use_ok"),
                    "The reference set's licence record",
                ),
                "reference",
                "scoring",
                f"reference:{reference.get('id')}",
            )
        )
    blockers = [i["name"] for i in items if i["presentable"] is not True]
    return {"items": items, "presentable": not blockers, "blockers": blockers}
