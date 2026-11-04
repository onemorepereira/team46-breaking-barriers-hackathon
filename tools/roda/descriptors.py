"""RODA facts (spike S1, awslabs.roda-mcp-server 0.1.7). Pure: no network, no SDK."""

from __future__ import annotations

SERVER = "roda"
PACKAGE = "awslabs.roda-mcp-server@0.1.7"
TOOL_NAMES = {
    "search_datasets",
    "list_datasets",
    "get_dataset_details",
    "discover_by_organization",
    "discover_by_license",
    "find_related_datasets",
    "get_knowledge_base_stats",
    "preview_dataset",
    "sample_dataset",
    "search_stac_endpoints",
}
# tool -> argument that names the dataset it opens
DATASET_ARG_FIELDS = {
    "get_dataset_details": "slug",
    "preview_dataset": "slug",
    "sample_dataset": "slug",
    "find_related_datasets": "slug",
}
# catalog searches find datasets but don't access one
SEARCH_TOOLS = {
    "search_datasets",
    "list_datasets",
    "discover_by_organization",
    "discover_by_license",
    "get_knowledge_base_stats",
    "search_stac_endpoints",
}


def dataset_from_args(tool: str, args: dict[str, object]) -> str | None:
    """The dataset a RODA tool call opened, or None for searches and tools that open none."""
    field = DATASET_ARG_FIELDS.get(tool)
    value = args.get(field) if field else None
    return str(value) if value else None
