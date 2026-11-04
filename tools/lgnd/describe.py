"""LGND Geo tool calls in plain English, for the console timeline and the judges' dossier. Pure."""

from __future__ import annotations

from typing import Any

from tools.lgnd.results import _json, _rows, chips_of

INDEX_NAMES = {"naip": "NAIP aerial imagery (US)", "s2": "Sentinel-2 imagery"}


def _index(args: dict[str, Any]) -> str:
    raw = args.get("scope")
    scope: dict[str, Any] = raw if isinstance(raw, dict) else {}
    idx = scope.get("index") or args.get("index")
    return INDEX_NAMES.get(str(idx), f"the '{idx}' index") if idx else "imagery"


def area_phrase(area: Any) -> str:
    """'within 50 km of 32.78, -96.80', 'inside a 412-point boundary', 'in a box …', or 'everywhere'."""
    if not isinstance(area, dict):
        return "everywhere (no area given)"
    if isinstance(area.get("ring"), list):
        return f"inside a {len(area['ring'])}-point boundary"
    if {"lat", "lon"} <= area.keys():
        r = area.get("radius_km")
        where = f"{float(area['lat']):.2f}, {float(area['lon']):.2f}"
        return f"within {r:g} km of {where}" if isinstance(r, int | float) else f"near {where}"
    if {"south", "north", "west", "east"} <= area.keys():
        return f"in the box {area['south']}..{area['north']} lat, {area['west']}..{area['east']} lon"
    return "in a custom area"


def _texts(args: dict[str, Any]) -> str:
    t = args.get("text") or args.get("query") or args.get("like")
    if isinstance(t, list):
        return " / ".join(f"'{x}'" for x in t)
    return f"'{t}'" if t else ""


def _best(chips: list[dict[str, Any]]) -> str:
    sims = [c["similarity"] for c in chips if isinstance(c.get("similarity"), int | float)]
    return f", best similarity {max(sims):.2f}" if sims else ""


def describe(name: str, args: dict[str, Any], result: str, status: str = "ok") -> str:
    args = args if isinstance(args, dict) else {}
    if status == "error":
        return f"LGND {name} failed: {result[:160].strip()}"
    data = _json(result) or {}
    chips = chips_of(data) if data else []
    raw = args.get("scope")
    scope: dict[str, Any] = raw if isinstance(raw, dict) else {}
    where = area_phrase(scope.get("area"))
    if name == "search_place_find":
        return f"Searched {_index(args)} for {_texts(args)} {where}: {len(chips)} matches{_best(chips)}."
    if name in ("search_change_find", "search_similar_change_find"):
        return f"Looked for changes in {_index(args)} {where}: {len(chips)} places{_best(chips)}."
    if name == "search_chip_lat_lon":
        return (
            f"Fetched the {_index(args)} chip at {args.get('lat')}, {args.get('lon')}"
            f"{' (observed ' + str(data['observed']) + ')' if data.get('observed') else ''}."
        )
    if name in ("discover_area_view", "discover_area_shift_find"):
        return f"Surveyed {_index(args)} {where}: {len(chips)} grid cells of ~{data.get('cell_km', '?')} km."
    if name == "toolbox_classifier_build":
        labels = data.get("labels") or args.get("examples") or {}
        return f"Trained classifier '{args.get('name')}' on {len(labels)} labels ({', '.join(labels)})."
    if name == "toolbox_classifier_apply":
        counts = data.get("counts") or {}
        tally = ", ".join(f"{k} {v}" for k, v in counts.items())
        return f"Applied classifier '{args.get('classifier')}' {where}: {tally or f'{len(chips)} results'}."
    if name == "reasoning_imagery_check":
        rows = _rows(data.get("places"))
        yes = sum(1 for r in rows if str(r.get("answer")).lower() == "yes")
        return (
            f"Asked the imagery reasoner to verify {len(rows)} places: {yes} yes, {len(rows) - yes} not; "
            f"verdict '{data.get('verdict', '?')}'."
        )
    if name in ("reasoning_chip_view", "reasoning_change_view"):
        return f"Showed a chip to the user ({args.get('chip_id') or args.get('node') or '?'})."
    if name == "user_alias_set":
        return f"Named {args.get('node')} as '{args.get('name')}'."
    if name == "user_identity_get":
        return "Checked the signed-in LGND identity."
    keys = ", ".join(f"{k}={str(v)[:30]}" for k, v in list(args.items())[:3])
    return f"Called LGND {name}({keys}): {result[:100].strip()}"
