"""Output scoring against a rubric file. Only the `none` scorer ships (spec: scoring method is open)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from analysis.trace import Run


@dataclass
class CriterionScore:
    criterion_id: str
    question: str
    score: float | None
    rationale: str


class Scorer(Protocol):
    name: str

    def score(self, run: Run, rubric: dict[str, Any]) -> list[CriterionScore]: ...


class NoneScorer:
    name = "none"

    def score(self, run: Run, rubric: dict[str, Any]) -> list[CriterionScore]:
        return [
            CriterionScore(
                str(c.get("id")), str(c.get("question", "")), None, "not scored (no evaluator configured)"
            )
            for c in rubric.get("criteria", [])
        ]


SCORERS: dict[str, Scorer] = {"none": NoneScorer()}


def score(run: Run) -> list[CriterionScore] | None:
    """Score from the rubric snapshotted in run.json (AC9: replay never reads current config)."""
    snap = run.manifest.get("snapshot") or {}
    rubric = snap.get("rubric")
    if not rubric:
        return None
    scorer = SCORERS.get(str(snap.get("scorer", "none")), SCORERS["none"])
    return scorer.score(run, rubric)
