"""AC7 summary: ordered steps, trouble spots (the single rule in design ADR-3), narrative filter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from analysis.provenance import MISMATCH, UNSOURCED, Provenance
from analysis.trace import MODEL_RESULT, RUN_END, TOOL_RESULT, Run

SPAN_ID_RE = re.compile(r"\b[0-9a-f]{16}\b")


@dataclass
class Step:
    span_id: str
    kind: str
    label: str
    detail: str


@dataclass
class TroubleSpot:
    span_id: str
    reason: str


@dataclass
class Summary:
    steps: list[Step]
    tools_used: list[str]
    trouble_spots: list[TroubleSpot]
    narrative: str | None = None
    narrative_dropped_ids: list[str] = field(default_factory=list)


def _step(span: Any) -> Step | None:
    if span.name == MODEL_RESULT:
        out = span.json_attr("harness.model.output", {}) or {}
        tool_uses = [
            c["toolUse"]["name"] for c in out.get("content", []) if isinstance(c, dict) and "toolUse" in c
        ]
        detail = (
            f"called {', '.join(tool_uses)}"
            if tool_uses
            else f"answered ({span.attr('harness.stop_reason')})"
        )
        return Step(span.span_id, "model", f"model call {span.attr('harness.model.call_index')}", detail)
    if span.name == TOOL_RESULT:
        attempt = int(span.attr("harness.tool.attempt", 0) or 0)
        label = f"{span.attr('harness.tool.ref')} {span.attr('harness.tool.name')}"
        detail = f"{span.attr('harness.tool.status')}" + (f", attempt {attempt}" if attempt else "")
        return Step(span.span_id, "tool", label, detail)
    return None


def trouble_spots(run: Run, prov: Provenance) -> list[TroubleSpot]:
    """The only trouble-spot rule (design ADR-3)."""
    spots: list[TroubleSpot] = []
    for s in run.spans:
        if s.status == "ERROR" and s.span_kind not in (
            "tool",
            "harness",
        ):  # tool failures: harness.tool_result
            spots.append(TroubleSpot(s.span_id, f"{s.name} ended with ERROR {s.status_message}".strip()))
    for s in run.tool_results:
        ref = s.attr("harness.tool.ref")
        if s.attr("harness.tool.status") == "error":
            spots.append(
                TroubleSpot(s.span_id, f"tool {ref} {s.attr('harness.tool.name')} returned an error")
            )
        if int(s.attr("harness.tool.attempt", 0) or 0) > 0:
            spots.append(
                TroubleSpot(s.span_id, f"tool {ref} retried (attempt {s.attr('harness.tool.attempt')})")
            )
        if s.attr("harness.tool.repeat_of"):
            spots.append(TroubleSpot(s.span_id, f"tool {ref} repeats {s.attr('harness.tool.repeat_of')}"))
    for s in run.model_results:
        if s.attr("harness.stop_reason") == "max_tokens":
            spots.append(TroubleSpot(s.span_id, "model output cut off at max_tokens"))
    if prov.claims_block_missing:
        spots.append(TroubleSpot(prov.anchor_span_id, "claims block missing from the final answer"))
    for c in prov.claims:
        if c.status in (MISMATCH, UNSOURCED):
            spots.append(TroubleSpot(c.span_id, f"claim '{c.claim}' = '{c.value}' is {c.status}"))
    end = [s for s in run.spans if s.name == RUN_END]
    if end and end[-1].attr("harness.status") == "limit_exceeded":
        spots.append(TroubleSpot(end[-1].span_id, "run ended: limit exceeded"))
    return spots


def build(run: Run, prov: Provenance) -> Summary:
    ordered = sorted(run.spans, key=lambda s: (s.start_ns, s.span_id))
    steps = [st for st in (_step(s) for s in ordered) if st]
    tools_used = sorted({str(s.attr("harness.tool.name")) for s in run.tool_results})
    narrative, dropped = None, []
    if run.summary and isinstance(run.summary.get("narrative"), str):
        narrative = run.summary["narrative"]
        dropped = list(run.summary.get("dropped_span_ids", []))
    return Summary(steps, tools_used, trouble_spots(run, prov), narrative, dropped)


def filter_narrative(text: str, known_ids: set[str]) -> tuple[str, list[str]]:
    """Remove span IDs the trace doesn't contain (ADR-3); return the cleaned text and what was dropped."""
    dropped: list[str] = []

    def repl(m: re.Match[str]) -> str:
        if m.group(0) in known_ids:
            return m.group(0)
        dropped.append(m.group(0))
        return "[unknown span]"

    return SPAN_ID_RE.sub(repl, text), dropped


def narrative_input(summary: Summary) -> str:
    """The only input the narrative model sees: the code-built structure (ADR-3)."""
    return json.dumps(
        {
            "steps": [s.__dict__ for s in summary.steps],
            "tools_used": summary.tools_used,
            "trouble_spots": [t.__dict__ for t in summary.trouble_spots],
        }
    )
