"""The archived run: spans, run.json, tool-result files, summary (design: Data and contracts)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from analysis.store import Store

STRANDS_SCOPE = "strands.telemetry.tracer"  # spike S1
HARNESS_SCOPE = "harness"
AGENT_SCOPES = {STRANDS_SCOPE, HARNESS_SCOPE}

# harness.* decision span names
RUN_START = "harness.run.start"
RUN_END = "harness.run.end"
MODEL_RESULT = "harness.model_result"
TOOL_RESULT = "harness.tool_result"

SPAN_CAP_BYTES = 16 * 1024


def span_kind_for(name: str) -> str:
    """Map a span name to harness.span_kind (design ADR-2; names from spike S1)."""
    if name.startswith("harness."):
        return "harness"
    if name.startswith("invoke_agent"):
        return "agent"
    if name == "execute_event_loop_cycle":
        return "cycle"
    if name == "chat":
        return "model"
    if name.startswith("execute_tool"):
        return "tool"
    return "other"


@dataclass(frozen=True)
class Span:
    span_id: str
    parent_span_id: str | None
    trace_id: str
    name: str
    scope: str
    kind: str
    start_ns: int
    end_ns: int
    status: str
    status_message: str
    attributes: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_line(cls, d: dict[str, Any]) -> Span:
        return cls(
            span_id=d["span_id"],
            parent_span_id=d.get("parent_span_id"),
            trace_id=d.get("trace_id", ""),
            name=d["name"],
            scope=d.get("scope", ""),
            kind=d.get("kind", ""),
            start_ns=int(d.get("start_ns", 0)),
            end_ns=int(d.get("end_ns", 0)),
            status=d.get("status", "UNSET"),
            status_message=d.get("status_message", "") or "",
            attributes=d.get("attributes", {}) or {},
            events=d.get("events", []) or [],
        )

    def attr(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    def json_attr(self, key: str, default: Any = None) -> Any:
        v = self.attributes.get(key)
        if v is None:
            return default
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return default
        return v

    @property
    def span_kind(self) -> str:
        return str(self.attributes.get("harness.span_kind") or span_kind_for(self.name))

    @property
    def is_agent_span(self) -> bool:
        return self.scope in AGENT_SCOPES and not self.attributes.get("harness.after_end")


class ArchiveError(Exception):
    pass


@dataclass
class Run:
    run_id: str
    store: Store
    manifest: dict[str, Any]
    result: dict[str, Any] | None
    summary: dict[str, Any] | None
    all_spans: list[Span]

    @classmethod
    def load(cls, store: Store, run_id: str) -> Run:
        prefix = f"runs/{run_id}"
        manifest_text = store.read_text(f"{prefix}/run.json")
        files = store.list(prefix)
        span_files = sorted(f for f in files if f.rsplit("/", 1)[-1].startswith("spans-"))
        if manifest_text is None and not span_files:
            raise ArchiveError(
                f"no archive for run {run_id} under {store.uri}/runs/. "
                "Check the run ID or archive_uri in harness.yaml."
            )
        spans: list[Span] = []
        for f in span_files:
            text = store.read_text(f) or ""
            for line in text.splitlines():
                if line.strip():
                    spans.append(Span.from_line(json.loads(line)))
        spans.sort(key=lambda s: (s.start_ns, s.span_id))
        result_text = store.read_text(f"{prefix}/result.json")
        summary_text = store.read_text(f"{prefix}/summary.json")
        manifest = json.loads(manifest_text) if manifest_text else {"run_id": run_id, "status": "unknown"}
        return cls(
            run_id=run_id,
            store=store,
            manifest=manifest,
            result=json.loads(result_text) if result_text else None,
            summary=json.loads(summary_text) if summary_text else None,
            all_spans=spans,
        )

    @cached_property
    def spans(self) -> list[Span]:
        """Agent spans only: Strands and harness scopes, excluding spans after harness.run.end."""
        return [s for s in self.all_spans if s.is_agent_span]

    def named(self, name: str) -> list[Span]:
        return [s for s in self.spans if s.name == name]

    @property
    def run_start(self) -> Span | None:
        found = self.named(RUN_START)
        return found[0] if found else None

    @property
    def run_end(self) -> Span | None:
        found = self.named(RUN_END)
        return found[-1] if found else None

    @property
    def model_results(self) -> list[Span]:
        return sorted(self.named(MODEL_RESULT), key=lambda s: int(s.attr("harness.model.call_index", 0)))

    @property
    def tool_results(self) -> list[Span]:
        return self.named(TOOL_RESULT)

    @property
    def status(self) -> str:
        if self.result and self.result.get("status"):
            return str(self.result["status"])
        return str(self.manifest.get("status", "unknown"))

    @property
    def final_output(self) -> str:
        if self.result and self.result.get("final_output") is not None:
            return str(self.result["final_output"])
        return str(self.manifest.get("final_output") or "")

    @property
    def partial(self) -> bool:
        return self.run_end is None or self.status not in ("ok",)

    def span_ids(self) -> set[str]:
        return {s.span_id for s in self.all_spans}

    def tool_result_text(self, span: Span) -> str | None:
        """The full, raw tool result from tool_results/<ref>.a<attempt>.txt (design ADR-AC6)."""
        uri = span.attr("harness.tool.result_uri")
        if not uri:
            return None
        key = str(uri)
        if not key.startswith("runs/"):
            key = f"runs/{self.run_id}/{key}"
        return self.store.read_text(key)
