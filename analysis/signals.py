"""AC8 workflow signals (raw numbers, no score) and AC2 datasets accessed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from analysis.trace import Run

# tool name -> argument field that names a dataset (spike S1: RODA uses `slug`)
DATASET_ARG_FIELDS: dict[str, str] = {
    "get_dataset_details": "slug",
    "preview_dataset": "slug",
    "sample_dataset": "slug",
    "find_related_datasets": "slug",
}


@dataclass
class Signals:
    steps: int
    model_calls: int
    tool_calls: int
    errors: int
    retries: int
    repeats: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model_latency_ms: int
    tool_latency_ms: int
    runtime_s: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def compute(run: Run) -> Signals:
    models, tools = run.model_results, run.tool_results
    in_tok = sum(int(s.attr("harness.usage.input_tokens", 0) or 0) for s in models)
    out_tok = sum(int(s.attr("harness.usage.output_tokens", 0) or 0) for s in models)
    errors = sum(1 for s in run.spans if s.status == "ERROR") + sum(
        1 for s in tools if s.attr("harness.tool.status") == "error"
    )
    prices = (run.manifest.get("snapshot") or {}).get("prices_per_mtok") or {}
    price = prices.get(run.manifest.get("model_key", ""))
    cost = None
    if (
        isinstance(price, dict)
        and isinstance(price.get("in"), int | float)
        and isinstance(price.get("out"), int | float)
    ):
        cost = round(in_tok / 1e6 * price["in"] + out_tok / 1e6 * price["out"], 6)
    start, end = _parse_ts(run.manifest.get("started_at")), _parse_ts(run.manifest.get("ended_at"))
    return Signals(
        steps=len(models) + len(tools),
        model_calls=len(models),
        tool_calls=len(tools),
        errors=errors,
        retries=sum(1 for s in tools if int(s.attr("harness.tool.attempt", 0) or 0) > 0),
        repeats=sum(1 for s in tools if s.attr("harness.tool.repeat_of")),
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=cost,
        model_latency_ms=sum(int(s.attr("harness.model.latency_ms", 0) or 0) for s in models),
        tool_latency_ms=sum(int(s.attr("harness.tool.latency_ms", 0) or 0) for s in tools),
        runtime_s=(end - start).total_seconds() if start and end else None,
    )


def tools_available(run: Run) -> list[dict[str, Any]]:
    start = run.run_start
    data = start.json_attr("harness.tools.available", []) if start else []
    return data if isinstance(data, list) else []


def datasets_accessed(run: Run) -> list[dict[str, str]]:
    """Datasets the agent opened by ID (tool arguments). Unmapped tools are listed as unknown."""
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for s in run.tool_results:
        name = str(s.attr("harness.tool.name", ""))
        args = s.json_attr("harness.tool.arguments", {}) or {}
        field = DATASET_ARG_FIELDS.get(name)
        if field and isinstance(args, dict) and args.get(field):
            key = (name, str(args[field]))
            seen.setdefault(key, {"dataset": str(args[field]), "via": name})
        elif not field:
            seen.setdefault((name, ""), {"dataset": "dataset unknown", "via": name})
    return list(seen.values())
