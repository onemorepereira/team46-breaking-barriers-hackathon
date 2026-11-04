"""Archive every span as JSONL the moment it ends, plus full tool results (design: Data and contracts).

Spans are serialized in `on_end`, before any later processor can change them. Uploads run on one
background writer thread, so the agent never waits on S3; `force_flush()` waits for the queue.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from agent import runctx
from core.store import Store

log = logging.getLogger("harness.archive")
FLUSH_EVERY = 50
_STOP = object()


def _otel_value(v: Any) -> Any:
    if isinstance(v, tuple | list):
        return [_otel_value(x) for x in v]
    return v


def serialize(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    parent = span.parent
    scope = span.instrumentation_scope.name if span.instrumentation_scope else ""
    return {
        "schema_version": 1,
        "scope": scope,
        "trace_id": f"{ctx.trace_id:032x}" if ctx else "",
        "span_id": f"{ctx.span_id:016x}" if ctx else "",
        "parent_span_id": f"{parent.span_id:016x}" if parent else None,
        "name": span.name,
        "kind": span.kind.name,
        "start_ns": span.start_time or 0,
        "end_ns": span.end_time or 0,
        "status": span.status.status_code.name,
        "status_message": span.status.description or "",
        "attributes": {k: _otel_value(v) for k, v in (span.attributes or {}).items()},
        "events": [
            {
                "name": e.name,
                "time_ns": e.timestamp,
                "attributes": {k: _otel_value(v) for k, v in e.attributes.items()},
            }
            for e in span.events
        ],
        "resource": {k: _otel_value(v) for k, v in (span.resource.attributes or {}).items()},
    }


class ArchiveWriter:
    """One background thread uploading (key, text) pairs with 3 attempts and backoff (1 s, 2 s, 4 s)."""

    def __init__(self, store: Store, backoff: tuple[float, ...] = (1, 2, 4)) -> None:
        self.store = store
        self.backoff = backoff
        self.errors = 0
        self._q: queue.Queue[Any] = queue.Queue()
        self._t = threading.Thread(target=self._loop, name="harness-archive", daemon=True)
        self._t.start()

    def put(self, key: str, text: str) -> None:
        self._q.put((key, text))

    def _loop(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is _STOP:
                    return
                key, text = item
                for i, delay in enumerate((0.0, *self.backoff)):
                    if delay:
                        time.sleep(delay)
                    try:
                        self.store.write_text(key, text)
                        break
                    except Exception as e:  # noqa: BLE001 - any write failure is counted, never raised
                        log.warning("archive write %s failed (attempt %d): %s", key, i + 1, e)
                else:
                    self.errors += 1
                    log.error("archive write %s failed after retries", key)
            finally:
                self._q.task_done()

    def wait(self, timeout_s: float = 60.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while self._q.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)
        return not self._q.unfinished_tasks


class ArchiveProcessor(SpanProcessor):
    def __init__(self, writer: ArchiveWriter) -> None:
        self.writer = writer
        self._lock = threading.Lock()
        self._buf: list[str] = []
        self._part = 0

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        return None

    def on_end(self, span: ReadableSpan) -> None:
        line = json.dumps(serialize(span), default=str)  # serialize now: later processors can't change it
        with self._lock:
            self._buf.append(line)
            if len(self._buf) >= FLUSH_EVERY:
                self._emit_locked()

    def _emit_locked(self) -> None:
        run_id = runctx.get("run_id")
        if not self._buf or not run_id:
            return
        self._part += 1
        self.writer.put(f"runs/{run_id}/spans-{self._part:04d}.jsonl", "\n".join(self._buf) + "\n")
        self._buf = []

    def start_run(self) -> None:
        with self._lock:
            self._buf, self._part = [], 0

    def force_flush(self, timeout_millis: int = 60000) -> bool:
        with self._lock:
            self._emit_locked()
        return self.writer.wait(timeout_millis / 1000)

    def shutdown(self) -> None:
        self.force_flush()
