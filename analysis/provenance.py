"""AC6 claim provenance: parse the claims block, resolve refs, grade each claim.

`analysis/provenance.py` is the only claims parser (design: Claims contract).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from analysis.trace import Run, Span

COORD_RE = re.compile(r"^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$")
NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")
NUMBER_IN_TEXT_RE = re.compile(r"-?\d+(?:\.\d+)?")
FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

MATCHED, MISMATCH, UNSOURCED = "matched", "mismatch", "unsourced"


@dataclass
class ClaimResult:
    claim: str
    value: str
    ref: str | None
    status: str
    span_id: str
    value_class: str
    notes: list[str] = field(default_factory=list)


@dataclass
class Provenance:
    claims_block_missing: bool
    claims: list[ClaimResult]
    anchor_span_id: str

    def counts(self) -> dict[str, int]:
        c = {MATCHED: 0, MISMATCH: 0, UNSOURCED: 0}
        for r in self.claims:
            c[r.status] += 1
        return c


def parse_claims_block(final_output: str) -> list[dict[str, Any]] | None:
    """Return the claims list from the last fenced JSON block containing "claims", or None."""
    for block in reversed(FENCE_RE.findall(final_output or "")):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("claims"), list):
            return [c for c in data["claims"] if isinstance(c, dict)]
    return None


UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
JSON_ESCAPES = {"\\n": " ", "\\t": " ", "\\r": " ", '\\"': '"', "\\/": "/"}


def unescape_json_text(s: str) -> str:
    """Tool results are often JSON, so the model reads `\\n` inside a string as a line break.

    Treat common JSON escapes as the characters they stand for (found in Build, live run 2e15c1bf).
    """
    for esc, ch in JSON_ESCAPES.items():
        s = s.replace(esc, ch)
    # \uXXXX escapes (JSON's way to write non-ASCII, e.g. "S\u00e3o Paulo"); found in Verify
    return UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), s)


def normalize_text(s: str) -> str:
    """NFC so composed and decomposed accents compare equal (Verify edge case), then casefold."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).strip().casefold())


def value_to_string(value: Any) -> tuple[str, bool]:
    """Claims must carry string values; a JSON number becomes its shortest decimal string."""
    if isinstance(value, str):
        return value.strip(), False
    if isinstance(value, bool) or value is None:
        return str(value), True
    if isinstance(value, int | float):
        return repr(value) if isinstance(value, float) else str(value), True
    return json.dumps(value), True


def classify(value: str) -> str:
    if COORD_RE.match(value):
        return "coordinate"
    if NUMBER_RE.match(value):
        return "number"
    return "text"


def _decimals(num: str) -> int:
    return len(num.split(".", 1)[1]) if "." in num else 0


def match_number(value: str, result: str) -> bool:
    if len(value) <= 2:
        # Short numbers must equal a whole numeric token (no tolerance).
        return re.search(rf"(?<![\d.]){re.escape(value)}(?![\d.])", result) is not None
    v = float(value)
    tol = 0.5 * 10 ** -_decimals(value) + 1e-12
    return any(abs(float(x) - v) <= tol for x in NUMBER_IN_TEXT_RE.findall(result))


def match_text(value: str, result: str) -> bool:
    v, r = normalize_text(value), normalize_text(unescape_json_text(result))
    if not v:
        return False
    if len(v) < 3:
        return re.search(rf"\b{re.escape(v)}\b", r) is not None
    return v in r


def matches(value: str, value_class: str, result: str) -> bool:
    if value_class == "coordinate":
        parts = [p.strip() for p in value.split(",")]
        return all(match_number(p, result) for p in parts)
    if value_class == "number":
        return match_number(value, result)
    return match_text(value, result)


def _latest_attempts(run: Run) -> dict[str, Span]:
    by_ref: dict[str, Span] = {}
    for span in run.tool_results:
        ref = span.attr("harness.tool.ref")
        if not ref:
            continue
        cur = by_ref.get(ref)
        if cur is None or int(span.attr("harness.tool.attempt", 0)) >= int(
            cur.attr("harness.tool.attempt", 0)
        ):
            by_ref[ref] = span
    return by_ref


def anchor_span(run: Run) -> str:
    """Where unsourced claims and a missing block link: the last model result, else run.start."""
    if run.model_results:
        return run.model_results[-1].span_id
    if run.run_start:
        return run.run_start.span_id
    return run.all_spans[0].span_id if run.all_spans else "-"


def grade(run: Run) -> Provenance:
    anchor = anchor_span(run)
    raw = parse_claims_block(run.final_output)
    if raw is None:
        return Provenance(claims_block_missing=True, claims=[], anchor_span_id=anchor)
    refs = _latest_attempts(run)
    out: list[ClaimResult] = []
    for item in raw:
        value, not_string = value_to_string(item.get("value"))
        ref = item.get("ref")
        ref = str(ref).strip() if isinstance(ref, str | int) and str(ref).strip() else None
        vclass = classify(value)
        notes = ["value_not_string"] if not_string else []
        span = refs.get(ref) if ref else None
        if span is None:
            out.append(ClaimResult(str(item.get("claim", "")), value, ref, UNSOURCED, anchor, vclass, notes))
            continue
        text = run.tool_result_text(span)
        if text is None:
            text = str(span.attr("harness.tool.result", ""))
            notes.append("full tool result missing from archive")
        status = MATCHED if matches(value, vclass, text) else MISMATCH
        out.append(ClaimResult(str(item.get("claim", "")), value, ref, status, span.span_id, vclass, notes))
    return Provenance(claims_block_missing=False, claims=out, anchor_span_id=anchor)
