"""Every decision span as one plain-English entry (spec AC11). Pure, no LLM.

Works on archived spans (analysis.trace.Span) and on console-exported span dicts (the live view), since both
come down to a span name plus its attributes.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from core.spans import MODEL_RESULT, RUN_END, RUN_START, TOOL_RESULT
from tools.describe import SERVER_LABELS, describe

FINAL_ANSWER = "Wrote the final answer."
SENTENCE_RE = re.compile(r"(.+?[.!?])(\s|$)", re.DOTALL)


@dataclass
class Entry:
    ref: str  # "M3" for model call 3, "T2" for the agent's tool ref, "start"/"end"
    kind: str  # model | tool | start | end
    title: str
    sentence: str
    status: str = "ok"
    server: str | None = None
    tool: str | None = None
    ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    attempt: int = 0
    span_id: str | None = None
    detail: str = ""  # longer plain text (reasoning or reply), shown expanded
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _loads(v: Any, default: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return default
    return v if v is not None else default


def first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    m = SENTENCE_RE.match(text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def model_ref(call_index: Any) -> str:
    i = _int(call_index)
    return f"M{(i or 0) + 1}"


def entry(
    name: str, a: dict[str, Any], span_id: str | None = None, raw: dict[str, Any] | None = None
) -> Entry | None:
    raw = raw if raw is not None else {"name": name, "attributes": a}
    if name == RUN_START:
        tools = _loads(a.get("harness.tools.available"), [])
        servers: dict[str, int] = {}
        for t in tools if isinstance(tools, list) else []:
            s = SERVER_LABELS.get(t.get("server"), t.get("server", "?"))
            servers[s] = servers.get(s, 0) + 1
        avail = ", ".join(f"{k} ({v} tools)" for k, v in servers.items()) or "no tools"
        return Entry(
            "start", "start", "Run started", f"The agent started with {avail}.", span_id=span_id, raw=raw
        )
    if name == MODEL_RESULT:
        out = _loads(a.get("harness.model.output"), {})
        content = out.get("content", []) if isinstance(out, dict) else []
        uses = [c["toolUse"] for c in content if isinstance(c, dict) and "toolUse" in c]
        text = "".join(c.get("text", "") for c in content if isinstance(c, dict) and "text" in c)
        reasoning = str(a.get("harness.reasoning.text") or "")
        thought = first_sentence(reasoning) if reasoning else ""
        if uses:
            names = ", ".join(str(u.get("name")) for u in uses)
            sentence = f"Decided to call {names}." + (f" Reasoning: {thought}" if thought else "")
        elif a.get("harness.stop_reason") == "max_tokens":
            sentence = "Ran out of output tokens mid-answer."
        else:
            sentence = FINAL_ANSWER + (f" {first_sentence(text)}" if text else "")
        detail = "\n\n".join(x for x in (reasoning.strip(), text.strip()) if x)
        ref = model_ref(a.get("harness.model.call_index"))
        return Entry(
            ref,
            "model",
            f"Model call {ref[1:]}",
            sentence,
            status="ok",
            ms=_int(a.get("harness.model.latency_ms")),
            tokens_in=_int(a.get("harness.usage.input_tokens")),
            tokens_out=_int(a.get("harness.usage.output_tokens")),
            span_id=span_id,
            detail=detail[:6000],
            raw=raw,
        )
    if name == TOOL_RESULT:
        server, tool = a.get("harness.tool.server"), str(a.get("harness.tool.name"))
        status = str(a.get("harness.tool.status") or "ok")
        result = str(a.get("harness.tool.result") or "")
        sentence = describe(server, tool, a.get("harness.tool.arguments"), result, status)
        if a.get("harness.tool.area_enforced"):
            sentence += " (The harness held this search to the requested boundary.)"
        if a.get("harness.tool.repeat_of"):
            sentence += f" Repeats {a.get('harness.tool.repeat_of')}."
        attempt = _int(a.get("harness.tool.attempt")) or 0
        ref = str(a.get("harness.tool.ref") or "T?")
        label = SERVER_LABELS.get(str(server), str(server or "tool"))
        return Entry(
            ref,
            "tool",
            f"{label} · {tool}",
            sentence,
            status=status,
            server=server,
            tool=tool,
            ms=_int(a.get("harness.tool.latency_ms")),
            attempt=attempt,
            span_id=span_id,
            raw=raw,
        )
    if name == RUN_END:
        st = str(a.get("harness.status") or "?")
        words = {
            "ok": "The run finished normally.",
            "limit_exceeded": "The run stopped at a budget limit.",
            "error": "The run ended with an error.",
        }
        return Entry(
            "end",
            "end",
            "Run ended",
            words.get(st, f"The run ended ({st})."),
            status=st,
            span_id=span_id,
            raw=raw,
        )
    return None


def entries(spans: list[Any]) -> list[Entry]:
    """Archived spans, in time order, as entries (decision spans only)."""
    out = []
    for s in sorted(spans, key=lambda s: (s.start_ns, s.span_id)):
        raw = {"span_id": s.span_id, "name": s.name, "status": s.status, "attributes": s.attributes}
        e = entry(s.name, s.attributes, s.span_id, raw)
        if e:
            out.append(e)
    return out
