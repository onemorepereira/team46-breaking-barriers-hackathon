"""The visual check's archived verdicts, read offline for scoring and display (docs/visual-check).

runs/<id>/visual.json is written by harness/visual.py when a run is judged; nothing here calls a model."""

from __future__ import annotations

import json
from typing import Any

from analysis.trace import Run

COUNTED = ("present", "absent", "unclear", "no_image", "error", "not_checked")


def load(run: Run) -> dict[str, Any] | None:
    text = run.store.read_text(f"runs/{run.run_id}/visual.json")
    if not text:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def summary(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Counts for the score, the caption and events: seen (present), checked (present + absent), the rest."""
    if not data:
        return None
    verdicts = [x.get("verdict") for x in data.get("sites") or [] if isinstance(x, dict)]
    count = {v: verdicts.count(v) for v in COUNTED}
    return {
        "status": data.get("status"),
        "reason": data.get("reason"),
        "sites": len(verdicts),
        "seen": count["present"],
        "checked": count["present"] + count["absent"],
        **count,
    }


def evaluate(run: Run) -> dict[str, Any] | None:
    """The summary plus `score` (seen / checked, None when nothing was confirmed or ruled out), or None."""
    s = summary(load(run))
    if s is None:
        return None
    return {**s, "score": s["seen"] / s["checked"] if s["checked"] and s["status"] != "error" else None}
