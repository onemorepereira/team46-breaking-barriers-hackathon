"""RODA tool calls in plain English, for the console timeline and the judges' dossier. Pure."""

from __future__ import annotations

import json
from typing import Any


def _json(result: str) -> dict[str, Any]:
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def describe(name: str, args: dict[str, Any], result: str, status: str = "ok") -> str:
    args = args if isinstance(args, dict) else {}
    if status == "error":
        return f"RODA {name} failed: {result[:160].strip()}"
    data = _json(result)
    slug = args.get("slug")
    if name == "search_datasets":
        found = data.get("total_count", data.get("returned_count", "?"))
        top = ", ".join(str(r.get("slug")) for r in (data.get("results") or [])[:3] if isinstance(r, dict))
        return (
            f"Searched the AWS Open Data registry for '{args.get('query')}': {found} datasets"
            f"{' (top: ' + top + ')' if top else ''}."
        )
    if name == "list_datasets":
        return f"Listed AWS Open Data datasets: {data.get('returned_count', data.get('total_count', '?'))}."
    if name == "get_dataset_details":
        return f"Read the details of dataset '{slug}' ({data.get('Name') or data.get('name') or '?'})."
    if name == "preview_dataset":
        return f"Listed files in dataset '{slug}': {data.get('object_count', '?')} objects."
    if name == "sample_dataset":
        return f"Read {data.get('bytes_read', '?')} bytes of '{args.get('file_key')}' from '{slug}'."
    if name == "find_related_datasets":
        return f"Found datasets related to '{slug}'."
    if name in ("discover_by_organization", "discover_by_license"):
        what = args.get("organization") or args.get("license")
        return f"Listed datasets for '{what}'."
    if name == "search_stac_endpoints":
        return f"Searched STAC endpoints for '{args.get('query', '')}'."
    keys = ", ".join(f"{k}={str(v)[:30]}" for k, v in list(args.items())[:3])
    return f"Called RODA {name}({keys}): {result[:100].strip()}"
