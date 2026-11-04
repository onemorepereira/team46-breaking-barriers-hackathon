"""Plain explanations of saved evidence, never a new judgement or model call.

Counts describe what the agent listed, not independently verified real-world sites.
The score and agreement label are kept separate from answer correctness.
"""

from __future__ import annotations

import re
from typing import Any

from analysis.judging.measure import Measured, measure
from analysis.judging.panel import PanelResult
from analysis.trace import Run
from tools.lgnd.results import extras

_DOUBTS = {
    "result_relevance": "Some results may not be what you asked for.",
    "grounding": "Some statements may go beyond what the tools showed.",
    "completeness": "Part of the request may be unanswered.",
    "calibration": "The answer may sound more certain than the evidence allows.",
    "tool_selection": "The chosen tools may not fully answer the request.",
    "tool_arguments": "Some search settings may not fit the request.",
    "sequencing_recovery": "Some steps were repeated or handled poorly.",
    "efficiency": "The run used more steps or resources than needed.",
}
_FAILURES = {
    "premature_fallback": "The agent may have given up on a useful approach too soon.",
    "overconfidence": _DOUBTS["calibration"],
    "retry_loop": "The agent repeated searches without enough new information.",
    "budget_abort": "The run stopped at a time or resource limit.",
    "proxy_substitution": "The answer may address an easier, different question.",
    "parametric_guess": "Some statements may come from memory rather than tool results.",
    "scope_violation": "Some work may fall outside the request.",
    "hallucinated_value": "Some reported values may have no source in the tool results.",
    "wrong_tool": _DOUBTS["tool_selection"],
    "incomplete_answer": _DOUBTS["completeness"],
}
_CHECKS = {
    "result_relevance": "Compare the listed results with the kind of feature you asked for.",
    "grounding": "Compare the answer's main statements with the saved tool results.",
    "completeness": "Read each part of your request and check that the answer covers it.",
    "calibration": "Check which results the answer calls confirmed and what supports that word.",
    "tool_selection": "Check that the tools used could answer your main question.",
    "tool_arguments": "Check the search area, dates, and result limits against your request.",
    "sequencing_recovery": "Check whether repeated searches added any useful evidence.",
    "efficiency": "Check whether repeated steps could be removed without losing evidence.",
}


def _short(text: str, words: int = 16) -> str:
    """Bound quoted labels; keep internal identifiers out of user-facing prose."""
    text = re.sub(r"\bT\d+\b", "", text).replace("_", " ")
    return " ".join(text.split()[:words])


def _image_checks(run: Run) -> tuple[int, int]:
    # A later check of the same node replaces an earlier check, rather than double-counting it.
    latest: dict[str, str] = {}
    for s in sorted(run.tool_results, key=lambda s: s.start_ns):
        if s.attr("harness.tool.status") in ("error", None):
            continue
        text = run.tool_result_text(s) or str(s.attr("harness.tool.result", ""))
        for v in extras(text).get("verdicts", []):
            latest[str(v["node"])] = str(v.get("answer") or "").strip().lower()
    no = sum(v == "no" for v in latest.values())
    unclear = sum(v not in ("yes", "no") for v in latest.values())
    return no, unclear


def explain(run: Run, result: PanelResult | None, *, measured: Measured | None = None) -> dict[str, Any]:
    """Explain the current saved result in at most 120 summary words, with 1–3 review actions."""
    m = measured or measure(run)
    points = {(x.lat, x.lon) for x in m.located if x.source == "claim"}
    n = len(points)
    found = (
        f"The agent listed {n} distinct {'location' if n == 1 else 'locations'}."
        if n
        else "The answer has no listed locations to count."
    )
    asked = f"Asked: {_short(run.prompt).rstrip('.!?')}." if run.prompt else "The request was not saved."
    facts = [asked, found]
    if m.area_compliance is not None:
        facts.append(
            f"{m.claims_inside} of {m.claims_located} location entries are inside "
            f"{_short(m.area_label or 'the requested area', 8)}."
        )
    if m.claims_total:
        facts.append(f"{m.claims_matched} of {m.claims_total} listed values matched the cited tool text.")

    doubts: list[str] = []
    checks: list[str] = []
    # These always survive the cut to three checks: condition reviews lead, recovery steps close.
    condition_checks: list[str] = []
    recovery: list[str] = []
    has_conditions = result is not None and any(c.id == "condition_compliance" for c in result.criteria)
    if run.not_scored:
        headline = "This run could not be scored because the AI service did not return a usable reply."
        facts = [asked, "The agent could not complete a usable AI call. It received no score."]
        recovery.append("Check service access and limits, then run the task again.")
    elif result is None:
        headline = "This run has not been judged yet."
        facts.append("Use Re-judge on this page to get a score.")
        recovery.append("Read the answer and use Re-judge to ask the judges to assess it.")
    elif result.verdict == "FAILED":
        headline = "This run failed to deliver a usable answer."
        facts.append("The run received 0/100.")
        ids = {g["id"] for g in result.gates}
        if "no_answer" in ids:
            doubts.append("It ended without a final answer.")
            recovery.append("Check why the run stopped before giving an answer, then try again.")
        if "no_tool_data" in ids:
            doubts.append("No tool returned usable data.")
            recovery.append("Check tool access and errors before trying again.")
    elif m.conditions_error and has_conditions:
        headline = "This evaluation is incomplete because the request conditions could not be read."
        facts.append("No overall score is available until the request conditions can be checked.")
        recovery.append("Check service access, then use Re-judge to retry reading the request conditions.")
    elif result.overall is None:
        headline = "There were not enough judge replies to give this run a score."
        facts.append("No score is available because too few judges returned usable replies.")
        recovery.append("Check judge access and try Re-judge again.")
    else:
        headline = f"The judges gave this run {result.overall:g}/100; review the evidence before using it."
        facts.append(
            f"The score is {result.overall:g}/100. Evidence agreement is {result.confidence.lower()}."
        )
        if not m.trace_integrity:
            doubts.append("Parts of the saved record are missing or could not be checked.")
            recovery.append("Restore the missing records before relying on this score.")
        if has_conditions and m.conditions_not_checked:
            doubts.append("The conditions in your request were not checked: no model is set to read them.")
            condition_checks.append(
                "Set narrative_model, then use Re-judge to check the conditions in your request."
            )
        elif has_conditions and m.condition_cap is not None and not m.conditions_total:
            doubts.append(
                "This request sets a distance condition but the run listed no locations, so output scored 0."
            )
            condition_checks.append(
                "If none found is the right answer, confirm it by hand; the score can't recognize it."
            )
        elif has_conditions and m.conditions_need_review:
            doubts.append("Some conditions in your request have no supporting evidence.")
            condition_checks.append(
                "Review each unverified or contradicted condition in the conditions table."
            )
        if result.confidence == "Medium" and result.judges_in_doubt:
            doubts.append("Some judge replies are missing or the judges disagree on parts of the work.")
        elif result.confidence == "Low" and m.trace_integrity:
            doubts.append("The judges disagree too much to rely on this score alone.")
        for f in result.failure_modes:
            if f["id"] in _FAILURES:
                doubts.append(_FAILURES[f["id"]])
        weakest = sorted(
            (c for c in result.criteria if c.kind == "judged" and c.score is not None and c.score < 100),
            key=lambda c: (c.score or 0, c.dimension != "output", c.id),
        )
        for c in weakest:
            doubts.append(_DOUBTS.get(c.id, "The judges found a weakness in part of the work."))
            checks.append(_CHECKS.get(c.id, "Read the judges' reasons for the lowest scores."))

    # Put concrete evidence gaps ahead of generic review suggestions.
    evidence_checks = []
    no, unclear = _image_checks(run)
    if no + unclear:
        evidence_checks.append(
            f"Review the {no + unclear} image checks that did not confirm a match "
            f"({no} no, {unclear} unclear)."
        )
    outside = m.claims_located - m.claims_inside
    if outside:
        noun = "location" if outside == 1 else "locations"
        evidence_checks.append(f"Check {outside} listed {noun} outside the area you asked for.")
    if m.claims_total > m.claims_matched or m.claims_block_missing:
        evidence_checks.append("Compare the listed values with their sources; some could not be matched.")
    reserved = [*condition_checks, *recovery]
    others = [c for c in dict.fromkeys([*evidence_checks, *checks]) if c not in reserved]
    checks = [*condition_checks, *others[: max(3 - len(reserved), 0)], *recovery]
    if not checks:
        checks = ["Check a few listed results against an independent source before using them."]
    if result and result.overall is not None and result.verdict != "FAILED":
        facts.append("Agreement and text matches do not prove the answer is correct.")
    # Whole sentences, so the word limit never hides the key distinction halfway through it.
    for sentence in list(dict.fromkeys(doubts))[:3]:
        if len(" ".join([*facts, sentence]).split()) <= 120:
            facts.append(sentence)
    return {"headline": headline, "summary": " ".join(facts), "check_by_hand": checks}
