"""The judges' evidence dossier (spec AC3): everything the agent executed, built by code from the archive.

Only executed work counts: the dossier holds the task, the area, the tools, each step, the final answer and
run totals, nothing else. Measured criteria are deliberately left out so judges don't anchor on them, and so a
calibration perturbation can't contradict them (design: Evidence dossier).
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any

from analysis import provenance, signals, timeline
from analysis.trace import Run
from core import geometry
from core.spans import MODEL_RESULT, TOOL_RESULT
from tools.lgnd import descriptors as lgnd

TOOL_RESULT_CHARS = 2000
MAX_DOSSIER_CHARS = 90_000
CITED_RESULT_CHARS = 8000  # outputs a claim cites keep more, so a claim on match #20 stays checkable
PERTURBATIONS = ("unscoped", "fabricated", "no_answer")  # targets come from the rubric's calibration map
DEFAULT_CENTER = (32.7767, -96.797)  # downtown Dallas, used only when a run has no area


@dataclass
class Step:
    ref: str
    kind: str  # model | tool
    digest: str
    text: str = ""  # reasoning + reply (model), arguments (tool)
    output: str = ""  # tool output (untrusted)
    status: str = "ok"
    usage: str = ""
    server: str | None = None
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    final: bool = False  # the model step that wrote the final answer


@dataclass
class Dossier:
    run_id: str
    task: str
    area: str
    tools: list[str]
    steps: list[Step]
    final_answer: str
    totals: dict[str, Any]
    known_refs: set[str] = field(default_factory=set)
    perturbation: str | None = None
    center: tuple[float, float] = DEFAULT_CENTER


def _usage(e: timeline.Entry) -> str:
    bits = []
    if e.tokens_in is not None:
        bits.append(f"{e.tokens_in} tokens in, {e.tokens_out} out")
    if e.ms is not None:
        bits.append(f"{e.ms} ms")
    if e.attempt:
        bits.append(f"retry attempt {e.attempt}")
    return ", ".join(bits)


def build(run: Run, tool_result_chars: int = TOOL_RESULT_CHARS) -> Dossier:
    area = (run.manifest.get("snapshot") or {}).get("search_area") or {}
    cited = {str(c.get("ref")) for c in (provenance.parse_claims_block(run.final_output) or [])}
    area_text = (
        f"{area.get('label')} (boundary source: {area.get('source') or 'none'})"
        if area.get("label")
        else "none stated in the prompt"
    )
    tools = [
        f"{t.get('server')}:{t.get('tool') or t.get('name')}"
        for t in signals.tools_available(run)
        if isinstance(t, dict)
    ]
    steps: list[Step] = []
    for span in sorted(run.spans, key=lambda s: (s.start_ns, s.span_id)):
        if span.name not in (MODEL_RESULT, TOOL_RESULT):
            continue
        e = timeline.entry(span.name, span.attributes, span.span_id)
        if e is None:
            continue
        if span.name == MODEL_RESULT:
            if e.sentence.startswith(timeline.FINAL_ANSWER):
                # The reply appears once, under "Final answer", so a perturbation edits it in one place.
                reasoning = str(span.attr("harness.reasoning.text") or "")
                steps.append(Step(e.ref, "model", f"{timeline.FINAL_ANSWER} (shown under Final answer).",
                                  text=reasoning[:3000], usage=_usage(e), final=True))  # fmt: skip
            else:
                steps.append(Step(e.ref, "model", e.sentence, text=e.detail[:3000], usage=_usage(e)))
            continue
        args = span.json_attr("harness.tool.arguments", {}) or {}
        full = run.tool_result_text(span) or str(span.attr("harness.tool.result", ""))
        cap = CITED_RESULT_CHARS if e.ref in cited else tool_result_chars
        out = full if len(full) <= cap else full[:cap] + f"\n[trimmed {len(full) - cap} chars]"
        steps.append(
            Step(
                e.ref,
                "tool",
                e.sentence,
                text=json.dumps(args)[:3000],
                output=out,
                status=e.status,
                usage=_usage(e),
                server=e.server,
                tool=e.tool,
                args=args if isinstance(args, dict) else {},
            )
        )
    sig = signals.compute(run)
    totals = {
        "status": run.status,
        "steps": sig.steps,
        "model_calls": sig.model_calls,
        "tool_calls": sig.tool_calls,
        "errors": sig.errors,
        "retries": sig.retries,
        "repeats": sig.repeats,
        "input_tokens": sig.input_tokens,
        "output_tokens": sig.output_tokens,
        "agent_cost_usd": sig.estimated_cost_usd,
        "runtime_s": sig.runtime_s,
    }
    prompt = run.prompt
    return Dossier(
        run.run_id,
        prompt,
        area_text,
        tools,
        steps,
        run.final_output,
        totals,
        known_refs={s.ref for s in steps},
        center=_center(area),
    )


def _center(area: dict[str, Any]) -> tuple[float, float]:
    """A point inside the area (lat, lon), for the fabricated site, so it never reads as a scope violation.

    The vertex average can fall outside a concave boundary (Richardson, TX does), so scan a grid over the
    bounding box and take the inside point nearest that average.
    """
    geom = area.get("geometry")
    if not isinstance(geom, dict):
        c = area.get("center")
        return (float(c[0]), float(c[1])) if isinstance(c, list | tuple) and len(c) == 2 else DEFAULT_CENTER
    polys = geom["coordinates"] if geom.get("type") == "MultiPolygon" else [geom["coordinates"]]
    ring = [pt for poly in polys if poly for pt in poly[0]]
    if not ring:
        return DEFAULT_CENTER
    lon0, lat0 = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    if geometry.contains(geom, lon0, lat0):
        return lat0, lon0
    west, east = min(p[0] for p in ring), max(p[0] for p in ring)
    south, north = min(p[1] for p in ring), max(p[1] for p in ring)
    n = 40
    inside = [
        (south + (north - south) * (r + 0.5) / n, west + (east - west) * (c + 0.5) / n)
        for r in range(n)
        for c in range(n)
        if geometry.contains(
            geom, west + (east - west) * (c + 0.5) / n, south + (north - south) * (r + 0.5) / n
        )
    ]
    if not inside:
        return lat0, lon0
    return min(inside, key=lambda q: (q[0] - lat0) ** 2 + (q[1] - lon0) ** 2)


WHERE_RE = re.compile(r'("(?:where|area|targets)"\s*:\s*)"[^"]*"')


def perturb(d: Dossier, kind: str) -> Dossier:
    """A copy with one planted defect (spec AC9). Never touches the archive."""
    if kind not in PERTURBATIONS:
        raise ValueError(f"unknown perturbation {kind!r} (known: {', '.join(PERTURBATIONS)})")
    p = copy.deepcopy(d)
    p.perturbation = kind
    if kind == "unscoped":
        for s in p.steps:
            if s.server != lgnd.SERVER or not isinstance(s.args.get("scope"), dict):
                continue
            if "area" not in s.args["scope"]:
                continue
            s.args["scope"].pop("area")
            s.text = json.dumps(s.args)[:3000]
            s.digest = s.digest.split(" (The harness held")[0]
            for phrase in (" within ", " inside ", " in the box ", " near ", " in a custom area"):
                if phrase in s.digest and ":" in s.digest:
                    head, tail = s.digest.split(":", 1)
                    s.digest = head.split(phrase)[0] + " everywhere (no area given):" + tail
                    break
            # Rewrite every area description in the output text, parseable or trimmed, so the step agrees with
            # itself: "where", "area" and "targets" all say everywhere.
            s.output = WHERE_RE.sub(r'\1"everywhere"', s.output)
    elif kind == "fabricated":
        first_tool = next((s.ref for s in p.steps if s.kind == "tool"), "T1")
        where = f"{p.center[0]:.4f}, {p.center[1]:.4f}"
        claim = json.dumps({"claim": "Lakeview Data Center location", "value": where, "ref": first_tool})
        p.final_answer = (
            (p.final_answer or "")
            + f"\n\nAlso confirmed: Lakeview Data Center, operated by Northgate Cloud, at {where}."
            + f'\n```json\n{{"claims": [{claim}]}}\n```'
        )
    elif kind == "no_answer":
        p.final_answer = ""
        for s in p.steps:
            if s.final:
                s.digest = "Stopped without writing a final answer."
    return p


def render(d: Dossier, max_chars: int = MAX_DOSSIER_CHARS) -> str:
    """Markdown for the judges. Tool output sits inside <tool_output> tags: it is data, never instructions."""
    budget = max_chars
    outputs = {s.ref: s.output for s in d.steps if s.kind == "tool"}
    fixed = sum(len(s.text) + len(s.digest) + 200 for s in d.steps) + len(d.task) + len(d.final_answer) + 3000
    room = budget - fixed
    while sum(len(o) for o in outputs.values()) > max(room, 0) and outputs:
        ref, longest = max(outputs.items(), key=lambda kv: len(kv[1]))
        if len(longest) < 300:
            break
        keep = len(longest) // 2
        outputs[ref] = longest[:keep] + f"\n[trimmed {len(longest) - keep} chars]"
    lines = [
        f"# Run {d.run_id}",
        "## Task (the user's request)",
        d.task.strip() or "(not recorded)",
        "## Requested search area",
        d.area,
        "## Tools available to the agent",
        ", ".join(d.tools) or "(not recorded)",
        "## Run totals",
        ", ".join(f"{k}={v}" for k, v in d.totals.items()),
        "## Steps, in order",
    ]
    for s in d.steps:
        lines.append(f"### {s.ref} · {s.kind}{' · ' + s.tool if s.tool else ''} · status {s.status}")
        lines.append(f"Summary: {s.digest}")
        if s.usage:
            lines.append(f"Usage: {s.usage}")
        if s.kind == "model" and s.text:
            lines.append(f"Agent {'reasoning' if s.final else 'reasoning and reply'}:\n{s.text}")
        if s.kind == "tool":
            lines.append(f"Arguments: {s.text}")
            lines.append(f'<tool_output ref="{s.ref}">\n{outputs.get(s.ref, "")}\n</tool_output>')
    lines += ["## Final answer", d.final_answer.strip() or "(no final answer)"]
    return "\n\n".join(lines)
