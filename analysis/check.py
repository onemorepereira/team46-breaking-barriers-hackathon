"""AC2 trace checker: every decision is recorded, and "full" content reassembles exactly.

Rules are the design's "Checker pass rules for full content (AC2)".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from analysis.trace import SPAN_CAP_BYTES, Run, Span

RUN_START_FIELDS = ("harness.tools.available",)
RUN_CONTEXT_FIELDS = ("harness.model.id", "harness.model.params", "harness.system_prompt.sha256")
MODEL_FIELDS = (
    "harness.model.call_index",
    "harness.model.input_messages_delta",
    "harness.model.input_message_count",
    "harness.model.output",
    "harness.usage.input_tokens",
    "harness.usage.output_tokens",
)
TOOL_FIELDS = (
    "harness.tool.ref",
    "harness.tool.server",
    "harness.tool.name",
    "harness.tool.arguments",
    "harness.tool.status",
    "harness.tool.latency_ms",
    "harness.tool.attempt",
    "harness.tool.result_uri",
    "harness.tool.result_sha256",
)


@dataclass(frozen=True)
class Missing:
    span_id: str
    kind: str
    field: str

    def line(self) -> str:
        return f"span {self.span_id} ({self.kind}): {self.field}"


def _missing_fields(span: Span, fields: tuple[str, ...]) -> list[Missing]:
    return [Missing(span.span_id, span.name, f) for f in fields if span.attributes.get(f) is None]


def check_run(run: Run) -> list[Missing]:
    out: list[Missing] = []
    start = run.run_start
    if start is None:
        out.append(Missing("-", "harness.run.start", "span missing"))
    else:
        out += _missing_fields(start, RUN_START_FIELDS)

    out += _check_models(run)
    out += _check_tools(run)
    return out


def _check_models(run: Run) -> list[Missing]:
    out: list[Missing] = []
    prev_count = 0
    for expected_index, span in enumerate(run.model_results):
        out += _missing_fields(span, RUN_CONTEXT_FIELDS + MODEL_FIELDS)
        idx = span.attr("harness.model.call_index")
        if idx is not None and int(idx) != expected_index:
            out.append(
                Missing(span.span_id, span.name, f"call_index gap (expected {expected_index}, got {idx})")
            )
        available = span.attr("harness.reasoning.available")
        if available is None:
            out.append(Missing(span.span_id, span.name, "harness.reasoning.available"))
        elif available and not span.attr("harness.reasoning.text"):
            out.append(Missing(span.span_id, span.name, "harness.reasoning.text"))
        if span.attr("harness.model.messages_trimmed"):
            out.append(Missing(span.span_id, span.name, "input messages trimmed (history not reassemblable)"))
        delta = span.json_attr("harness.model.input_messages_delta")
        count = span.attr("harness.model.input_message_count")
        if isinstance(delta, list) and count is not None:
            if len(delta) != int(count) - prev_count:
                out.append(
                    Missing(
                        span.span_id,
                        span.name,
                        f"input_messages_delta length {len(delta)} != count {count} - previous {prev_count}",
                    )
                )
            prev_count = int(count)
    return out


def _check_tools(run: Run) -> list[Missing]:
    out: list[Missing] = []
    for span in run.tool_results:
        out += _missing_fields(span, TOOL_FIELDS)
        if span.attr("harness.tool.result_uri") is None:
            continue
        text = run.tool_result_text(span)
        if text is None:
            out.append(Missing(span.span_id, span.name, "tool result file missing from archive"))
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != span.attr("harness.tool.result_sha256"):
            out.append(Missing(span.span_id, span.name, "tool result file hash mismatch"))
        truncated = bool(span.attr("harness.tool.result_truncated"))
        if truncated != (len(text.encode("utf-8")) > SPAN_CAP_BYTES):
            out.append(
                Missing(span.span_id, span.name, "harness.tool.result_truncated inconsistent with file size")
            )
    return out


def full_input(run: Run, call_index: int) -> list[object]:
    """Reassemble the full input messages for a model call (concatenated deltas 0..i)."""
    msgs: list[object] = []
    for span in run.model_results[: call_index + 1]:
        msgs.extend(span.json_attr("harness.model.input_messages_delta", []))
    return msgs


def as_json(missing: list[Missing]) -> str:
    return json.dumps([m.__dict__ for m in missing])
