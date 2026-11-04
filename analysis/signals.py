"""AC8 workflow signals (raw numbers, no score) and AC2 datasets accessed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from analysis.trace import Run
from tools.lgnd import descriptors as lgnd
from tools.roda import descriptors as roda


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
    # A failed tool shows up twice: Strands' execute_tool span (ERROR) and our harness.tool_result. Count
    # tool failures once, from harness.tool_result, plus ERROR spans of other kinds (agent, cycle, model).
    errors = sum(
        1 for s in run.spans if s.status == "ERROR" and s.span_kind not in ("tool", "harness")
    ) + sum(1 for s in tools if s.attr("harness.tool.status") == "error")
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
    """Datasets the agent opened by ID. Catalog searches don't count; unmapped tools are listed as unknown."""
    seen: dict[str, set[str]] = {}
    for s in run.tool_results:
        name = str(s.attr("harness.tool.name", ""))
        args = s.json_attr("harness.tool.arguments", {}) or {}
        if not isinstance(args, dict) or name in roda.SEARCH_TOOLS:
            continue
        server = s.attr("harness.tool.server")
        found = (
            lgnd.dataset_from_args(name, args)
            if server == lgnd.SERVER
            else roda.dataset_from_args(name, args)
        )
        dataset = found or f"dataset unknown ({name})"
        seen.setdefault(dataset, set()).add(name)
    return [{"dataset": d, "via": ", ".join(sorted(v))} for d, v in seen.items()]
