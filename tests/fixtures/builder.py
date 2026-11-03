"""Build synthetic archives in the exact layout the agent writes (design: Data and contracts)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from analysis.trace import HARNESS_SCOPE, SPAN_CAP_BYTES, STRANDS_SCOPE, span_kind_for

SYSTEM_SHA = "a" * 64
PROMPT_SHA = "b" * 64
MODEL_ID = "us.anthropic.claude-haiku-5-5"
MODEL_PARAMS = {
    "max_tokens": 16000,
    "request_fields": {"thinking": {"type": "adaptive", "display": "summarized"}},
}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class RunBuilder:
    root: Path
    run_id: str = "run-0001"
    suite_id: str | None = None
    model_key: str = "haiku"
    model_id: str = MODEL_ID
    t: int = 1_000_000_000
    _n: int = 0
    lines: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    model_calls: int = 0
    refs: dict[str, str] = field(default_factory=dict)
    tools_available: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"server": "roda", "tool": "search_datasets", "input_schema": {}},
            {"server": "roda", "tool": "get_dataset_details", "input_schema": {}},
        ]
    )

    @property
    def run_dir(self) -> Path:
        return self.root / "runs" / self.run_id

    def _id(self) -> str:
        self._n += 1
        return f"{self._n:016x}"

    def _tick(self, ms: int = 10) -> int:
        self.t += ms * 1_000_000
        return self.t

    def span(
        self,
        name: str,
        attrs: dict[str, Any] | None = None,
        *,
        scope: str = HARNESS_SCOPE,
        status: str = "OK",
        status_message: str = "",
        dur_ms: int = 5,
        events: list[dict[str, Any]] | None = None,
        drop: tuple[str, ...] = (),
    ) -> str:
        sid = self._id()
        start = self._tick()
        base = {
            "harness.run_id": self.run_id,
            "harness.suite_id": self.suite_id,
            "harness.prompt.sha256": PROMPT_SHA,
            "harness.system_prompt.sha256": SYSTEM_SHA,
            "harness.model.id": self.model_id,
            "harness.model.params": json.dumps(MODEL_PARAMS),
            "harness.span_kind": span_kind_for(name),
        }
        base.update(attrs or {})
        for k in drop:
            base.pop(k, None)
        self.lines.append(
            {
                "schema_version": 1,
                "scope": scope,
                "trace_id": "f" * 32,
                "span_id": sid,
                "parent_span_id": None,
                "name": name,
                "kind": "INTERNAL",
                "start_ns": start,
                "end_ns": start + dur_ms * 1_000_000,
                "status": status,
                "status_message": status_message,
                "attributes": base,
                "events": events or [],
                "resource": {},
            }
        )
        return sid

    # --- decision spans -------------------------------------------------
    def run_start(self) -> str:
        self.messages.append({"role": "user", "content": [{"text": "Find data centers near Dallas, TX."}]})
        return self.span(
            "harness.run.start",
            {
                "harness.tools.available": json.dumps(self.tools_available),
                "harness.limits": json.dumps({"max_steps": 40}),
            },
        )

    def strands(self, name: str, status: str = "OK") -> str:
        return self.span(name, scope=STRANDS_SCOPE, status=status)

    def model(
        self,
        output_text: str,
        *,
        reasoning: str | None = "Thinking about which datasets to search.",
        in_tok: int = 1000,
        out_tok: int = 100,
        stop_reason: str = "end_turn",
        tool_use: dict[str, Any] | None = None,
        trim: bool = False,
        drop: tuple[str, ...] = (),
        delta_override: list[Any] | None = None,
        call_index: int | None = None,
    ) -> str:
        self.strands("chat")
        prev = getattr(self, "_prev_count", 0)
        count = len(self.messages)
        delta = self.messages[prev:count]
        self._prev_count = count
        content: list[dict[str, Any]] = []
        if reasoning:
            content.append({"reasoningContent": {"reasoningText": {"text": reasoning}}})
        if output_text:
            content.append({"text": output_text})
        if tool_use:
            content.append({"toolUse": tool_use})
        output = {"role": "assistant", "content": content}
        self.messages.append(output)
        attrs: dict[str, Any] = {
            "harness.model.call_index": self.model_calls if call_index is None else call_index,
            "harness.model.input_messages_delta": json.dumps(
                delta if delta_override is None else delta_override
            ),
            "harness.model.input_message_count": count,
            "harness.model.output": json.dumps(output),
            "harness.reasoning.available": bool(reasoning),
            "harness.reasoning.kind": "summarized",
            "harness.stop_reason": stop_reason,
            "harness.usage.input_tokens": in_tok,
            "harness.usage.output_tokens": out_tok,
            "harness.model.latency_ms": 900,
        }
        if reasoning:
            attrs["harness.reasoning.text"] = reasoning
        if trim:
            attrs["harness.model.messages_trimmed"] = True
        self.model_calls += 1
        return self.span("harness.model_result", attrs, drop=drop)

    def tool(
        self,
        name: str,
        arguments: dict[str, Any],
        result: str,
        *,
        status: str = "success",
        attempt: int = 0,
        ref: str | None = None,
        repeat_of: str | None = None,
        write_file: bool = True,
        corrupt_hash: bool = False,
        drop: tuple[str, ...] = (),
        span_status: str = "OK",
    ) -> tuple[str, str]:
        ref = ref or f"T{len(self.refs) + 1}"
        use_id = self.refs.setdefault(ref, f"tooluse_{ref}")
        self.strands(f"execute_tool {name}", status=span_status)
        uri = f"tool_results/{ref}.a{attempt}.txt"
        if write_file:
            p = self.run_dir / uri
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(result, encoding="utf-8")
        attrs: dict[str, Any] = {
            "harness.tool.ref": ref,
            "harness.tool.use_id": use_id,
            "harness.tool.server": "roda",
            "harness.tool.name": name,
            "harness.tool.arguments": json.dumps(arguments),
            "harness.tool.result": result[:SPAN_CAP_BYTES],
            "harness.tool.result_sha256": ("0" * 64) if corrupt_hash else sha256(result),
            "harness.tool.result_uri": uri,
            "harness.tool.result_truncated": len(result.encode("utf-8")) > SPAN_CAP_BYTES,
            "harness.tool.status": status,
            "harness.tool.latency_ms": 1200,
            "harness.tool.attempt": attempt,
        }
        if repeat_of:
            attrs["harness.tool.repeat_of"] = repeat_of
        sid = self.span("harness.tool_result", attrs, drop=drop)
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": use_id, "content": [{"text": f"[ref {ref}] {result}"}]}}
                ],
            }
        )
        return sid, ref

    def run_end(self, status: str = "ok") -> str:
        return self.span(
            "harness.run.end",
            {
                "harness.status": status,
                "harness.tool_refs": json.dumps(self.refs),
                "harness.archive_errors": 0,
            },
        )

    # --- files ------------------------------------------------------------
    def write(
        self,
        *,
        final_output: str,
        status: str = "ok",
        write_result: bool = True,
        prices: dict[str, Any] | None = None,
        rubric: dict[str, Any] | None = None,
        started_at: str = "2026-11-04T15:00:00Z",
        ended_at: str = "2026-11-04T15:01:30Z",
        part_size: int = 50,
    ) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for i in range(0, len(self.lines), part_size):
            part = self.lines[i : i + part_size]
            (self.run_dir / f"spans-{i // part_size + 1:04d}.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in part), encoding="utf-8"
            )
        manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "suite_id": self.suite_id,
            "backend": "local",
            "model_key": self.model_key,
            "model_id": self.model_id,
            "prompt_file": "prompts/dallas-dc.md",
            "prompt_sha256": PROMPT_SHA,
            "started_at": started_at,
            "ended_at": ended_at,
            "status": status,
            "final_output": final_output,
            "archive_uri": f"file://{self.root}",
            "archive_errors": 0,
            "snapshot": {
                "prices_per_mtok": prices or {"haiku": {"in": 1.0, "out": 5.0}},
                "rubric": rubric,
                "scorer": "none",
                "harness_version": "test",
            },
        }
        (self.run_dir / "run.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        if write_result:
            result = {
                "schema_version": 1,
                "run_id": self.run_id,
                "status": status,
                "error": None,
                "final_output": final_output,
                "tool_refs": self.refs,
                "archive_errors": 0,
            }
            (self.run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
        return self.run_dir


CLAIMS_OK = """Equinix DA11 is a data center in Dallas at latitude 32.80.

```json
{"claims": [
  {"claim": "Equinix operates DA11", "value": "Equinix", "ref": "T1"},
  {"claim": "DA11 latitude", "value": "32.80", "ref": "T1"},
  {"claim": "Number of sites", "value": "3", "ref": "T1"}
]}
```"""

DA11_RESULT = (
    '{"results": [{"name": "DA11", "operator": "Equinix", "address": "1950 N Stemmons Fwy", '
    '"lat": 32.8008, "lon": -96.8195, "sites": 3, "slug": "osm-datacenters"}]}'
)


def standard_run(root: Path, run_id: str = "run-0001", **kw: Any) -> RunBuilder:
    """A complete, healthy run: 2 model calls, 1 tool call, 3 matched claims."""
    b = RunBuilder(root=root, run_id=run_id, **kw)
    b.run_start()
    b.strands("invoke_agent Strands Agents")
    b.strands("execute_event_loop_cycle")
    b.model("", tool_use={"toolUseId": "tooluse_T1", "name": "get_dataset_details", "input": {"slug": "osm"}})
    b.tool("get_dataset_details", {"slug": "osm-datacenters"}, DA11_RESULT)
    b.model(CLAIMS_OK, in_tok=2000, out_tok=300)
    b.run_end("ok")
    b.write(final_output=CLAIMS_OK)
    return b
