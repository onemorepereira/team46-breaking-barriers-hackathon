"""HarnessHooks: reference labels, decision spans, limits, cooperative cancel (design: Agent internals).

Every decision becomes a small `harness.*` span that ends immediately, emitted from the same explicit
provider as Strands' spans. Event fields come from spike S1 (strands-agents 1.63.0).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from strands.hooks import (
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from agent.archive import ArchiveWriter
from agent.telemetry import to_attr
from core import geometry
from core.spans import SPAN_CAP_BYTES
from tools.lgnd import descriptors as lgnd


class LimitExceeded(Exception):
    pass


def _result_text(result: dict[str, Any]) -> str:
    parts = []
    for block in result.get("content", []) or []:
        if isinstance(block, dict) and "text" in block:
            parts.append(str(block["text"]))
        elif isinstance(block, dict) and "json" in block:
            parts.append(json.dumps(block["json"]))
    return "\n".join(parts)


def _cap(text: str, limit: int = SPAN_CAP_BYTES) -> str:
    data = text.encode("utf-8")
    return text if len(data) <= limit else data[:limit].decode("utf-8", errors="ignore")


class HarnessHooks(HookProvider):
    def __init__(
        self,
        *,
        tracer: Any,
        writer: ArchiveWriter,
        run_id: str,
        tools_available: list[dict[str, Any]],
        limits: dict[str, Any],
        server_of: dict[str, str],
        search_area: dict[str, Any] | None = None,
    ) -> None:
        self.tracer = tracer
        self.writer = writer
        self.run_id = run_id
        self.tools_available = tools_available
        self.limits = limits
        self.server_of = server_of
        self.search_area = search_area or {}
        self._area_requested: dict[str, Any] = {}  # tool_use_id -> the area the model asked for
        self.cancel = threading.Event()
        # Claude on Bedrock returns summarized thinking; other models (e.g. Kimi K3) return their own.
        self.reasoning_kind = "summarized" if "anthropic" in str(limits.get("model_id", "")) else "native"
        self.emitted = 0
        self.limit_reason: str | None = None
        self._lock = threading.Lock()
        self.steps = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_input_tokens = 0
        self.call_index = 0
        self._prev_count = 0
        self._model_started = 0.0
        self._pending_delta: list[Any] = []
        self._pending_count = 0
        self._trimmed = False
        self.refs: dict[str, str] = {}  # ref -> tool_use_id
        self._ref_of: dict[str, str] = {}  # tool_use_id -> ref
        self._attempts: dict[str, int] = {}
        self._first_ref_for_call: dict[str, str] = {}
        self._repeat_of: dict[str, str] = {}
        self._tool_started: dict[str, float] = {}
        self._tool_args: dict[str, Any] = {}

    # --- spans --------------------------------------------------------------
    def emit(self, name: str, attrs: dict[str, Any]) -> str:
        span = self.tracer.start_span(
            name, attributes={k: to_attr(v) for k, v in attrs.items() if v is not None}
        )
        span.end()
        self.emitted += 1
        return f"{span.get_span_context().span_id:016x}"

    def run_start(self) -> None:
        self.emit(
            "harness.run.start",
            {"harness.tools.available": self.tools_available, "harness.limits": self.limits},
        )

    def run_end(self, status: str, archive_errors: int) -> None:
        self.emit(
            "harness.run.end",
            {
                "harness.status": status,
                "harness.tool_refs": self.refs,
                "harness.archive_errors": archive_errors,
                "harness.decision_spans_emitted": self.emitted + 1,  # including this run.end span
            },
        )

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self.before_model)
        registry.add_callback(AfterModelCallEvent, self.after_model)
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    # --- limits ---------------------------------------------------------------
    def _check(self, *, projected_input: int = 0) -> None:
        reason = None
        if self.cancel.is_set():
            reason = "wall clock exceeded"
        elif self.steps >= int(self.limits["max_steps"]):
            reason = f"step limit {self.limits['max_steps']} reached"
        elif self.input_tokens + max(projected_input, self.last_input_tokens) > int(
            self.limits["max_input_tokens"]
        ):
            reason = f"input token limit {self.limits['max_input_tokens']} reached"
        elif self.output_tokens + int(self.limits.get("max_tokens", 0)) > int(
            self.limits["max_output_tokens"]
        ):
            reason = f"output token limit {self.limits['max_output_tokens']} reached"
        if reason:
            self.limit_reason = self.limit_reason or reason
            raise LimitExceeded(reason)

    # --- model ----------------------------------------------------------------
    def before_model(self, event: BeforeModelCallEvent) -> None:
        with self._lock:
            self._blocked = False
            try:
                self._check(projected_input=int(getattr(event, "projected_input_tokens", 0) or 0))
            except LimitExceeded:
                self._blocked = True  # the call never reaches the model; after_model must not record it
                raise
            self.steps += 1
            messages = event.agent.messages
            count = len(messages)
            if count < self._prev_count:
                self._trimmed = True
            self._pending_delta = json.loads(json.dumps(messages[self._prev_count : count], default=str))
            self._pending_count = count
            self._model_started = time.monotonic()

    def after_model(self, event: AfterModelCallEvent) -> None:
        with self._lock:
            if getattr(self, "_blocked", False):
                self._blocked = False
                return
            latency_ms = int((time.monotonic() - self._model_started) * 1000)
            resp = event.stop_response
            message = dict(resp.message) if resp is not None else None
            content = (message or {}).get("content", []) or []
            reasoning = "".join(
                str(c["reasoningContent"].get("reasoningText", {}).get("text", ""))
                for c in content
                if isinstance(c, dict) and "reasoningContent" in c
            )
            usage = ((message or {}).get("metadata") or {}).get("usage") or {}
            # Converse reports cached prompt tokens outside inputTokens (seen with Kimi K3's automatic
            # caching), so total input = uncached + cache read + cache write. Undercounting would weaken
            # the input-token cap and the cost estimate.
            cache_read = int(usage.get("cacheReadInputTokens", 0) or 0)
            cache_write = int(usage.get("cacheWriteInputTokens", 0) or 0)
            in_tok = int(usage.get("inputTokens", 0) or 0) + cache_read + cache_write
            out_tok = int(usage.get("outputTokens", 0) or 0)
            self.input_tokens += in_tok
            self.output_tokens += out_tok
            self.last_input_tokens = in_tok
            attrs: dict[str, Any] = {
                "harness.model.call_index": self.call_index,
                "harness.model.input_messages_delta": self._pending_delta,
                "harness.model.input_message_count": self._pending_count,
                "harness.model.output": message if message is not None else {},
                "harness.reasoning.available": bool(reasoning),
                "harness.reasoning.text": reasoning or None,
                "harness.reasoning.kind": self.reasoning_kind,
                "harness.stop_reason": str(resp.stop_reason) if resp is not None else "error",
                "harness.usage.input_tokens": in_tok,
                "harness.usage.output_tokens": out_tok,
                "harness.usage.cache_read_input_tokens": cache_read,
                "harness.usage.cache_write_input_tokens": cache_write,
                "harness.model.latency_ms": latency_ms,
            }
            if event.exception is not None:
                attrs["harness.model.error"] = str(event.exception)
            if self._trimmed:
                attrs["harness.model.messages_trimmed"] = True
            self.emit("harness.model_result", attrs)
            self.call_index += 1
            self._prev_count = self._pending_count

    # --- tools ----------------------------------------------------------------
    def before_tool(self, event: BeforeToolCallEvent) -> None:
        with self._lock:
            self._check()
            self.steps += 1
            use = event.tool_use
            use_id = str(use.get("toolUseId"))
            if use_id not in self._ref_of:
                ref = f"T{len(self.refs) + 1}"
                self._ref_of[use_id], self.refs[ref] = ref, use_id
                self._attempts[use_id] = 0
                key = f"{use.get('name')}|{json.dumps(use.get('input'), sort_keys=True, default=str)}"
                if key in self._first_ref_for_call:
                    self._repeat_of[use_id] = self._first_ref_for_call[key]
                else:
                    self._first_ref_for_call[key] = ref
            else:
                self._attempts[use_id] += 1
            self._enforce_area(event, use_id)
            self._tool_args[use_id] = event.tool_use.get("input")
            self._tool_started[use_id] = time.monotonic()

    def _enforce_area(self, event: BeforeToolCallEvent, use_id: str) -> None:
        """Enforce mode: LGND searches run inside the prompt's official boundary. The model may narrow a
        search to a smaller area inside it (every outline point inside the boundary); anything else, or no
        area at all, is replaced by the boundary, and the model's request is recorded."""
        area = self.search_area.get("lgnd_area")
        use = event.tool_use
        name = str(use.get("name"))
        inp = dict(use.get("input") or {})
        if self.search_area.get("mode") != "enforce" or not area or self.server_of.get(name) != lgnd.SERVER:
            return
        if not lgnd.reads_area(name, inp):
            return
        scope = dict(inp.get("scope") or {})
        boundary = self.search_area.get("geometry")
        outline = lgnd.area_outline(scope.get("area"))
        if boundary and outline and all(geometry.contains(boundary, lon, lat) for lon, lat in outline):
            return  # a narrower search inside the boundary: kept as sent
        self._area_requested[use_id] = scope.get("area")
        scope["area"] = area
        inp["scope"] = scope
        event.tool_use = {**use, "input": inp}  # type: ignore[assignment]

    def after_tool(self, event: AfterToolCallEvent) -> None:
        with self._lock:
            use = event.tool_use
            use_id = str(use.get("toolUseId"))
            ref = self._ref_of.get(use_id) or "T?"
            attempt = self._attempts.get(use_id, 0)
            result = dict(event.result or {})
            raw = _result_text(result)
            if event.exception is not None and not raw:
                raw = f"error: {event.exception}"
            status = (
                "error" if (event.exception is not None or result.get("status") == "error") else "success"
            )
            uri = f"tool_results/{ref}.a{attempt}.txt"
            self.writer.put(f"runs/{self.run_id}/{uri}", raw)
            started = self._tool_started.get(use_id, time.monotonic())
            duration = getattr(event, "duration", None)
            latency_ms = int((duration if duration is not None else time.monotonic() - started) * 1000)
            name = str(use.get("name"))
            self.emit(
                "harness.tool_result",
                {
                    "harness.tool.ref": ref,
                    "harness.tool.use_id": use_id,
                    "harness.tool.server": self.server_of.get(name, "local"),
                    "harness.tool.name": name,
                    "harness.tool.arguments": self._tool_args.get(use_id, use.get("input")),
                    "harness.tool.result": _cap(raw),
                    "harness.tool.result_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    "harness.tool.result_uri": uri,
                    "harness.tool.result_truncated": len(raw.encode("utf-8")) > SPAN_CAP_BYTES,
                    "harness.tool.status": status,
                    "harness.tool.latency_ms": latency_ms,
                    "harness.tool.attempt": attempt,
                    "harness.tool.repeat_of": self._repeat_of.get(use_id),
                    "harness.tool.area_enforced": use_id in self._area_requested or None,
                    "harness.tool.area_requested": (
                        self._area_requested.get(use_id) if use_id in self._area_requested else None
                    ),
                },
            )
            # What the model sees: the ref label, and at most 16 KB of the result.
            visible = _cap(raw)
            if len(visible) < len(raw):
                visible += f"\n[truncated; full result archived as {ref}]"
            result["content"] = [{"text": f"[ref {ref}] {visible}"}]
            result.pop("structuredContent", None)
            event.result = result  # type: ignore[assignment]
