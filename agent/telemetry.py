"""One tracer provider per process; the exporter is chosen only by HARNESS_EXPORTER (design ADR-1).

adot    -> ADOT (opentelemetry-instrument) owns the global provider; we add our processors to it.
otlp    -> OTLP/HTTP, configured by the standard OTEL_EXPORTER_OTLP_* variables.
console -> JSON lines to HARNESS_CONSOLE_PATH, or stderr (never stdout).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from agent import runctx
from agent.archive import ArchiveProcessor, ArchiveWriter
from analysis.store import open_store
from analysis.trace import span_kind_for

RUN_ATTRS = {
    "harness.run_id": "run_id",
    "harness.suite_id": "suite_id",
    "harness.prompt.sha256": "prompt_sha256",
    "harness.system_prompt.sha256": "system_prompt_sha256",
    "harness.model.id": "model_id",
    "harness.model.params": "model_params_json",
}


class RunContextProcessor(SpanProcessor):
    """Sets run-level attributes on every span in on_start, while the span is still mutable."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        ctx = runctx.snapshot()
        attrs: dict[str, Any] = {k: ctx[v] for k, v in RUN_ATTRS.items() if ctx.get(v) is not None}
        attrs["harness.span_kind"] = span_kind_for(span.name)
        if ctx.get("ended"):
            attrs["harness.after_end"] = True
        span.set_attributes(attrs)

    def on_end(self, span: ReadableSpan) -> None:
        return None


@dataclass
class Telemetry:
    provider: Any
    archive: ArchiveProcessor
    writer: ArchiveWriter

    def tracer(self) -> trace.Tracer:
        tracer: trace.Tracer = self.provider.get_tracer("harness")
        return tracer


_current: Telemetry | None = None


def setup() -> Telemetry:
    """Idempotent: the provider is created once per process and never replaced."""
    global _current
    if _current is not None:
        return _current
    exporter = os.environ.get("HARNESS_EXPORTER", "console")
    writer = ArchiveWriter(open_store(os.environ.get("HARNESS_ARCHIVE_URI", "file://./archive")))
    archive = ArchiveProcessor(writer)
    if exporter == "adot":
        provider = trace.get_tracer_provider()  # installed by opentelemetry-instrument (ADOT)
        provider.add_span_processor(RunContextProcessor())  # type: ignore[attr-defined]
        provider.add_span_processor(archive)  # type: ignore[attr-defined]
    else:
        provider = TracerProvider(sampler=ALWAYS_ON)
        provider.add_span_processor(RunContextProcessor())
        provider.add_span_processor(archive)
        if exporter == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        elif exporter == "console":
            path = os.environ.get("HARNESS_CONSOLE_PATH")
            out = open(path, "a", encoding="utf-8") if path else sys.stderr  # noqa: SIM115 - lives for the process
            provider.add_span_processor(
                SimpleSpanProcessor(
                    ConsoleSpanExporter(out=out, formatter=lambda s: s.to_json(indent=None) + "\n")
                )
            )
        elif exporter != "none":
            raise ValueError(f"unknown HARNESS_EXPORTER {exporter!r}; use adot, otlp or console")
        # Strands' tracer reads the global provider (spike S1), so set it once, then hand it over.
        trace.set_tracer_provider(provider)
    from strands.telemetry import StrandsTelemetry

    StrandsTelemetry(tracer_provider=provider)  # type: ignore[arg-type]
    _current = Telemetry(provider=provider, archive=archive, writer=writer)
    return _current


def flush_exporters() -> None:
    if _current is not None and hasattr(_current.provider, "force_flush"):
        _current.provider.force_flush()


def to_attr(value: Any) -> Any:
    """OTel attributes must be primitives; dicts and lists of dicts become JSON."""
    if isinstance(value, str | bool | int | float):
        return value
    return json.dumps(value, default=str)
