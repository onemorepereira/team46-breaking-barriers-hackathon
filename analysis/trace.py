"""The archived run: spans, run.json, tool-result files, summary (design: Data and contracts)."""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from core.spans import (
    AGENT_SCOPES,
    MODEL_RESULT,
    RUN_END,
    RUN_START,
    SPAN_CAP_BYTES,
    TOOL_RESULT,
    span_kind_for,
)
from core.store import Store

__all__ = ["SPAN_CAP_BYTES", "ArchiveError", "Run", "Span"]


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


class _LRU:
    """Bounded, thread-safe cache of immutable archive objects, by total characters."""

    def __init__(self, max_chars: int) -> None:
        self.max_chars, self.size = max_chars, 0
        self.items: OrderedDict[tuple[str, str], str] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: tuple[str, str]) -> str | None:
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
            return None

    def put(self, key: tuple[str, str], text: str) -> None:
        if len(text) > self.max_chars // 4:
            return
        with self.lock:
            if key in self.items:
                return
            self.items[key] = text
            self.size += len(text)
            while self.size > self.max_chars:
                _, old = self.items.popitem(last=False)
                self.size -= len(old)


_ARCHIVE_CACHE = _LRU(200_000_000)  # ~200 MB of write-once archive objects (tool results, span chunks)


@dataclass
class Run:
    run_id: str
    store: Store
    manifest: dict[str, Any]
    result: dict[str, Any] | None
    summary: dict[str, Any] | None
    all_spans: list[Span]
    _tool_text: dict[str, str | None] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def load(cls, store: Store, run_id: str) -> Run:
        prefix = f"runs/{run_id}"
        # Every object is its own S3 GET (~100 ms): fetch the listing and the fixed files together, then
        # all span files together, instead of one after another.
        with ThreadPoolExecutor(max_workers=16) as pool:
            fixed = pool.map(
                store.read_text, [f"{prefix}/{n}" for n in ("run.json", "result.json", "summary.json")]
            )
            files = store.list(prefix)
            span_files = sorted(f for f in files if f.rsplit("/", 1)[-1].startswith("spans-"))
            cached = {f: _ARCHIVE_CACHE.get((store.uri, f)) for f in span_files}
            fetched = dict(
                zip(
                    todo := [f for f, t in cached.items() if t is None],
                    pool.map(store.read_text, todo),
                    strict=True,
                )
            )
            span_texts = [cached[f] if cached[f] is not None else fetched[f] for f in span_files]
            manifest_text, result_text, summary_text = list(fixed)
        manifest_status = (json.loads(manifest_text) if manifest_text else {}).get("status")
        if manifest_status not in (None, "running", "unknown"):
            # A finished run's span chunks are each written once (agent/archive.py numbers them).
            for f, text in fetched.items():
                if text is not None:
                    _ARCHIVE_CACHE.put((store.uri, f), text)
        if manifest_text is None and not span_files:
            raise ArchiveError(
                f"no archive for run {run_id} under {store.uri}/runs/. "
                "Check the run ID or archive_uri in harness.yaml."
            )
        spans: list[Span] = []
        for text in span_texts:
            for line in (text or "").splitlines():
                if line.strip():
                    spans.append(Span.from_line(json.loads(line)))
        spans.sort(key=lambda s: (s.start_ns, s.span_id))
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

    @cached_property
    def prompt(self) -> str:
        """The user's prompt: run.json (newer runs), else the first model call's input messages."""
        if self.manifest.get("prompt"):
            return str(self.manifest["prompt"])
        first = self.model_results[0] if self.model_results else None
        msgs = first.json_attr("harness.model.input_messages_delta", []) if first else []
        for m in msgs if isinstance(msgs, list) else []:
            for c in m.get("content", []) if isinstance(m, dict) else []:
                if isinstance(c, dict) and c.get("text"):
                    return str(c["text"])
        return ""

    @cached_property
    def _judgement_record(self) -> dict[str, Any] | None:
        text = self.store.read_text(f"runs/{self.run_id}/judgement.json")
        return json.loads(text) if text else None

    @property
    def judgement(self) -> dict[str, Any] | None:
        """runs/<id>/judgement.json (docs/judging); None if never judged, or not scored."""
        rec = self._judgement_record
        return None if rec is None or rec.get("not_scored") else rec

    @property
    def unrevised_judgement(self) -> dict[str, Any] | None:
        """The first judgement before any human-prompted revision (docs/judge-feedback): agreement among
        judges must not count votes a reviewer influenced. Follows `revision.previous` into judgements/."""
        jd = self.judgement
        seen = 0
        while jd and jd.get("revision") and seen < 20:
            prev = (jd["revision"] or {}).get("previous")
            text = self.store.read_text(f"runs/{self.run_id}/judgements/{prev}.json") if prev else None
            if not text:
                return None
            jd = json.loads(text)
            seen += 1
        return jd

    @property
    def not_scored(self) -> dict[str, Any] | None:
        """{"reason", "cause"} when the panel declined the run (an infrastructure error), else None."""
        rec = self._judgement_record
        return rec.get("not_scored") if rec else None

    def tool_result_text(self, span: Span) -> str | None:
        """The full, raw tool result from tool_results/<ref>.a<attempt>.txt (design ADR-AC6)."""
        uri = span.attr("harness.tool.result_uri")
        if not uri:
            return None
        key = self._tool_key(uri)
        if key not in self._tool_text:
            self._prefetch_tool_results(key)
        return self._tool_text.get(key)

    def _tool_key(self, uri: Any) -> str:
        key = str(uri)
        return key if key.startswith("runs/") else f"runs/{self.run_id}/{key}"

    def _prefetch_tool_results(self, wanted: str) -> None:
        """Read every tool result of the run at once, in parallel (one S3 GET each, ~100 ms apiece, was
        serial and dominated opening a run). Results are write-once (<ref>.a<attempt>.txt), so they are
        also kept in a bounded process-wide cache and reopening a run doesn't fetch them again."""
        keys = {wanted} | {
            self._tool_key(u) for s in self.all_spans if (u := s.attr("harness.tool.result_uri"))
        }
        missing = []
        for k in keys:
            hit = _ARCHIVE_CACHE.get((self.store.uri, k))
            if hit is not None:
                self._tool_text[k] = hit
            else:
                missing.append(k)
        if not missing:
            return
        with ThreadPoolExecutor(max_workers=min(16, len(missing))) as pool:
            texts = list(pool.map(self.store.read_text, missing))
        for k, text in zip(missing, texts, strict=True):
            self._tool_text[k] = text
            if text is not None:
                _ARCHIVE_CACHE.put((self.store.uri, k), text)
