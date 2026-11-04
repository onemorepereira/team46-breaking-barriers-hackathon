"""Human feedback for the judges, the pure parts (docs/judge-feedback/design.md).

Shapes and validation for reviews and guidance, the human score per (run, criterion), how guidance renders
into the judge prompt, and agreement between the panel and humans. No I/O: harness/feedback.py stores
and calls models.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

from analysis.judging.alpha import alpha
from analysis.judging.rubric import Rubric

REASON_MAX = 2000
NOTE_MAX = 4000
LESSON_MAX = 400
LESSONS_MAX = 12
GUIDANCE_CHARS_MAX = 8000  # about 2,000 tokens (spec: prompt budget)
NAME_MAX = 80
SPECIFIC_RE = re.compile(r"\b[MT]\d+\b|[0-9a-f]{8}-[0-9a-f]{4}-")  # step IDs, run IDs: not general


class FeedbackError(ValueError):
    """A review, lesson or guidance version that can't be accepted; the message says why."""


def _name(value: Any, what: str) -> str:
    s = str(value or "").strip()
    if not s:
        raise FeedbackError(f"{what} is required.")
    if len(s) > NAME_MAX:
        raise FeedbackError(f"{what} is longer than {NAME_MAX} characters.")
    return s


def panel_medians(judgement: dict[str, Any], r: Rubric) -> dict[str, float]:
    """Pass-1 lower median per judged criterion, from the valid votes (what the reviewer saw)."""
    passes = judgement.get("passes") or []
    out: dict[str, float] = {}
    if not passes:
        return out
    valid = [j for j in passes[0].get("judges", []) if j.get("status") == "ok"]
    for c in r.judged:
        votes = sorted(int(j["scores"][c.id]) for j in valid if c.id in (j.get("scores") or {}))
        if votes:
            out[c.id] = float(votes[(len(votes) - 1) // 2])
    return out


def validate_review(body: dict[str, Any], r: Rubric, known_refs: set[str],
                    judgement: dict[str, Any]) -> dict[str, Any]:  # fmt: skip
    """Check a submitted review; return its reviewer and normalized criteria. Raises FeedbackError."""
    reviewer = _name(body.get("reviewer"), "Your name")
    raw = body.get("criteria") or {}
    if not isinstance(raw, dict):
        raise FeedbackError("criteria must be an object keyed by criterion id.")
    judged = {c.id for c in r.judged}
    medians = panel_medians(judgement, r)
    out: dict[str, dict[str, Any]] = {}
    unknown_refs: list[str] = []
    for cid, item in raw.items():
        if cid not in judged:
            measured = {c.id for c in r.measured}
            why = "is measured by code; use the measured-checks note" if cid in measured else "isn't judged"
            raise FeedbackError(f"{cid} {why}.")
        if not isinstance(item, dict):
            raise FeedbackError(f"{cid}: expected an object.")
        agree = bool(item.get("agree"))
        refs = [str(x).strip() for x in item.get("refs") or [] if str(x).strip()]
        unknown_refs += [x for x in refs if x not in known_refs]
        entry: dict[str, Any] = {"agree": agree, "panel_median": medians.get(cid)}
        if agree:
            if medians.get(cid) is None:
                raise FeedbackError(f"{cid}: the panel has no score to agree with.")
            entry["score"] = medians[cid]
        else:
            try:
                score = int(item.get("score"))  # type: ignore[arg-type]
            except (TypeError, ValueError) as e:
                raise FeedbackError(f"{cid}: pick a score from {list(r.scale)}.") from e
            if score not in r.scale:
                raise FeedbackError(f"{cid}: pick a score from {list(r.scale)}.")
            reason = str(item.get("reason") or "").strip()
            if not reason:
                raise FeedbackError(f"{cid}: say why you disagree.")
            if len(reason) > REASON_MAX:
                raise FeedbackError(f"{cid}: the reason is longer than {REASON_MAX} characters.")
            entry.update(score=float(score), reason=reason)
        if refs:
            entry["refs"] = refs
        out[cid] = entry
    if unknown_refs:
        raise FeedbackError(f"Unknown step IDs: {', '.join(sorted(set(unknown_refs)))}.")
    if not out:
        raise FeedbackError("Review at least one criterion.")
    for k in ("note", "measured_note"):
        if len(str(body.get(k) or "")) > NOTE_MAX:
            raise FeedbackError(f"{k} is longer than {NOTE_MAX} characters.")
    return {"reviewer": reviewer, "criteria": out}


def escape(text: str) -> str:
    """Neutralize tag-like text in human input before it goes inside <human_review> or <review> tags, or into
    one of their attributes."""
    return str(text).replace("&", "&amp;").replace("<", "‹").replace(">", "›").replace('"', "”")


def render_review(review: dict[str, Any]) -> str:
    """The review as the judges see it in reconsideration: each criterion with the human score and reason."""
    lines = []
    for cid, c in review.get("criteria", {}).items():
        if c.get("agree"):
            lines.append(f"- {cid}: the reviewer agrees with the panel ({c.get('score')}).")
            continue
        refs = f" Steps cited: {', '.join(c['refs'])}." if c.get("refs") else ""
        lines.append(
            f"- {cid}: the reviewer would score {int(c['score'])} (panel: {c.get('panel_median')}). "
            f"Reason: {escape(c.get('reason', ''))}{refs}"
        )
    note = str(review.get("note") or "").strip()
    if note:
        lines.append(f"Overall note: {escape(note)}")
    return "\n".join(lines)


# ---- Guidance ----


def validate_lessons(raw: Any, r: Rubric, known_reviews: set[str] | None,
                     require_sources: bool) -> tuple[list[dict[str, Any]], int]:  # fmt: skip
    """Normalize lessons. With `known_reviews`, sources must be real reviews. Returns (lessons, dropped).

    Proposal drops bad lessons (require_sources=True); a hand edit raises instead (check_edit)."""
    if not isinstance(raw, list):
        raise FeedbackError("lessons must be a list.")
    judged = {c.id for c in r.judged}
    out: list[dict[str, Any]] = []
    dropped = 0
    for item in raw:
        if not isinstance(item, dict):
            dropped += 1
            continue
        cid = str(item.get("criterion") or "")
        text = " ".join(str(item.get("text") or "").split())
        sources = [str(s) for s in item.get("sources") or [] if str(s).strip()]
        if known_reviews is not None:
            sources = [s for s in sources if s in known_reviews]
        if (
            cid not in judged
            or not text
            or len(text) > LESSON_MAX
            or SPECIFIC_RE.search(text)
            or (require_sources and not sources)
        ):
            dropped += 1
            continue
        lesson = {"id": f"L{len(out) + 1}", "criterion": cid, "text": text, "sources": sorted(set(sources))}
        out.append(lesson)
    if len(out) > LESSONS_MAX:
        dropped += len(out) - LESSONS_MAX
        out = out[:LESSONS_MAX]
    return out, dropped


def check_edit(raw: Any, r: Rubric, known_reviews: set[str]) -> list[dict[str, Any]]:
    """A hand edit of a draft's lessons: every lesson must be valid (sources optional, but real)."""
    if not isinstance(raw, list):
        raise FeedbackError("lessons must be a list.")
    judged = {c.id for c in r.judged}
    for i, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise FeedbackError(f"Lesson {i}: expected an object.")
        if str(item.get("criterion") or "") not in judged:
            raise FeedbackError(f"Lesson {i}: pick a judged criterion ({', '.join(sorted(judged))}).")
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            raise FeedbackError(f"Lesson {i}: the text is empty.")
        if len(text) > LESSON_MAX:
            raise FeedbackError(f"Lesson {i}: longer than {LESSON_MAX} characters.")
        if SPECIFIC_RE.search(text):
            raise FeedbackError(f"Lesson {i}: name no step or run IDs; a lesson must hold for any run.")
        bad = [str(s) for s in item.get("sources") or [] if str(s) not in known_reviews]
        if bad:
            raise FeedbackError(f"Lesson {i}: unknown review {', '.join(bad)}.")
    if len(raw) > LESSONS_MAX:
        raise FeedbackError(f"At most {LESSONS_MAX} lessons.")
    lessons, _ = validate_lessons(raw, r, known_reviews, require_sources=False)
    if len(render_lessons(lessons, r)) > GUIDANCE_CHARS_MAX:
        raise FeedbackError(f"The lessons are longer than the {GUIDANCE_CHARS_MAX}-character prompt budget.")
    return lessons


def guidance_sha(version: dict[str, Any]) -> str:
    body = {"rubric": version.get("rubric"), "lessons": version.get("lessons") or []}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


GUIDANCE_HEAD = "  Clarifications from human review (they refine the anchors above and never override them):"


def lessons_for(lessons: list[dict[str, Any]], cid: str) -> list[str]:
    return [f"  - {x['id']}: {x['text']}" for x in lessons if x.get("criterion") == cid]


def render_lessons(lessons: list[dict[str, Any]], r: Rubric) -> str:
    """Every lesson block as it appears in the prompt (used for the size budget)."""
    blocks = []
    for c in r.judged:
        lines = lessons_for(lessons, c.id)
        if lines:
            blocks.append("\n".join([GUIDANCE_HEAD, *lines]))
    return "\n".join(blocks)


def held_out(run_id: str) -> bool:
    """The fixed train / held-out split (design: Train and held-out runs): about a third of runs are held out,
    chosen by run ID, so it's stable as reviews arrive and the same on every machine."""
    return int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % 3 == 0


# ---- Human scores and agreement ----


def lower_median(values: list[float]) -> float:
    v = sorted(values)
    return float(v[(len(v) - 1) // 2])


def human_scores(reviews: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """run_id -> criterion -> {"human", "panel", "reviewers", "review_ids", "guidance_version", "judged_at"}.

    Per run, only reviews of the most recently reviewed judgement count, the latest per reviewer. The human
    score is the lower median across those reviewers (on the scale, like the panel's); the panel score is that
    judgement's pass-1 median, as recorded in the reviews (design: Evaluation, step 1)."""
    by_run: dict[str, list[dict[str, Any]]] = {}
    for rv in reviews:
        by_run.setdefault(rv["run_id"], []).append(rv)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for run_id, rvs in by_run.items():
        target = max(str(rv.get("judged_at") or "") for rv in rvs)
        latest: dict[str, dict[str, Any]] = {}
        for rv in sorted(rvs, key=lambda x: x.get("created_at", "")):
            if str(rv.get("judged_at") or "") == target:
                latest[rv["reviewer"].casefold()] = rv
        per_c: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        for rv in latest.values():
            for cid, c in rv.get("criteria", {}).items():
                if c.get("score") is not None:
                    per_c.setdefault(cid, []).append((rv, c))
        for cid, items in per_c.items():
            panel = next((c["panel_median"] for _, c in items if c.get("panel_median") is not None), None)
            out.setdefault(run_id, {})[cid] = {
                "human": lower_median([float(c["score"]) for _, c in items]),
                "panel": None if panel is None else float(panel),
                "reviewers": sorted({rv["reviewer"] for rv, _ in items}),
                "review_ids": sorted(rv["id"] for rv, _ in items),
                "guidance_version": items[-1][0].get("guidance_version"),
                "judged_at": target,
            }
    return out


def mad_and_exact(pairs: list[tuple[float, float]]) -> dict[str, Any]:
    if not pairs:
        return {"mad": None, "exact": None, "n": 0}
    return {
        "mad": round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3),
        "exact": round(sum(1 for a, b in pairs if a == b) / len(pairs), 3),
        "n": len(pairs),
    }


def human_agreement(scores: dict[str, dict[str, dict[str, Any]]], samples: int = 1000,
                    seed: int = 7) -> dict[str, Any]:  # fmt: skip
    """Panel vs humans: ordinal alpha with two coders (panel median, human score) over (run, criterion) units,
    a cluster-bootstrap CI over runs, and the mean absolute difference. Grouped by guidance version."""
    groups: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for run_id, crit in scores.items():
        for c in crit.values():
            if c.get("panel") is None:
                continue
            key = "none" if c.get("guidance_version") is None else str(c["guidance_version"])
            groups.setdefault(key, {}).setdefault(run_id, []).append((c["panel"], c["human"]))
    out = {}
    for key, runs in sorted(groups.items()):
        pairs = [p for ps in runs.values() for p in ps]
        a = alpha([[p[0] for p in pairs], [p[1] for p in pairs]])
        entry: dict[str, Any] = {"alpha": None if a is None else round(a, 3), "ci95": None, "runs": len(runs),
                                 **mad_and_exact(pairs)}  # fmt: skip
        if len(runs) >= 2:
            rng = random.Random(seed)
            ids = list(runs)
            boots = []
            for _ in range(samples):
                s = [p for _ in ids for p in runs[ids[rng.randrange(len(ids))]]]
                b = alpha([[p[0] for p in s], [p[1] for p in s]])
                if b is not None:
                    boots.append(b)
            boots.sort()
            if boots:
                entry["ci95"] = [round(boots[int(0.025 * len(boots))], 3),
                                 round(boots[int(0.975 * len(boots)) - 1], 3)]  # fmt: skip
        out[key] = entry
    return {"by_guidance": out}


def compare(rows: list[dict[str, Any]], max_rise: float = 0.25) -> dict[str, Any]:
    """Evaluation metrics. rows: {"run_id", "criterion", "human", "without", "with"} (panel medians).

    Verdict inputs (design: Evaluation, step 6): overall MAD must drop; no criterion's may rise > max_rise.
    """
    by_c: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_c.setdefault(row["criterion"], []).append(row)

    def metrics(rs: list[dict[str, Any]], key: str) -> dict[str, Any]:
        return mad_and_exact([(r[key], r["human"]) for r in rs if r.get(key) is not None])

    per = {}
    rises = []
    for cid, rs in sorted(by_c.items()):
        w, g = metrics(rs, "without"), metrics(rs, "with")
        per[cid] = {"without": w, "with": g}
        if w["mad"] is not None and g["mad"] is not None and g["mad"] - w["mad"] > max_rise:
            rises.append(cid)
    overall = {"without": metrics(rows, "without"), "with": metrics(rows, "with")}
    ow, og = overall["without"]["mad"], overall["with"]["mad"]
    return {"criteria": per, "overall": overall, "improved": ow is not None and og is not None and og < ow,
            "rises": rises}  # fmt: skip
