"""Quick human feedback on a displayed evaluation, separate from scored rubric reviews.

These records never enter judge prompts, guidance training, or score calculations.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from core.store import Store
from harness import feedback


def _key(run_id: str, response_id: str) -> str:
    if not re.fullmatch(r"q-[0-9a-f]{24}", response_id):
        raise feedback.NotFound("unknown quick feedback")
    return f"feedback/reactions/{run_id}/{response_id}.json"


def list_for(store: Store, run_id: str, judged_at: str | None) -> list[dict[str, Any]]:
    records = []
    for key in store.list(f"feedback/reactions/{run_id}/"):
        rv = feedback._read(store, key) if key.endswith(".json") else None
        if rv:
            records.append({**rv, "current": rv.get("judged_at") == judged_at})
    return sorted(records, key=lambda rv: rv["created_at"], reverse=True)


def save(store: Store, run_id: str, card: dict[str, Any] | None, body: dict[str, Any]) -> dict[str, Any]:
    if not card or card.get("overall") is None:
        raise feedback.Conflict("There is no evaluation score to review yet.")
    if not body.get("judged_at") or body["judged_at"] != card.get("judged_at"):
        raise feedback.Conflict("The judgement changed. Refresh and review the current score.")
    target = body["target"]
    scores = {
        "overall": card["overall"],
        **card.get("dimensions", {}),
        **{c["id"]: c["score"] for c in card.get("criteria", [])},
    }
    if target not in scores or scores[target] is None:
        raise feedback.fb.FeedbackError("Choose a scored evaluation criterion.")
    rv = {
        "id": f"q-{secrets.token_hex(12)}",
        "run_id": run_id,
        "judged_at": body["judged_at"],
        "target": target,
        "vote": body["vote"],
        "score": scores[target],
        "rubric": card.get("rubric"),
        "comment": "",
        "created_at": feedback.now(),
    }
    feedback._write(store, _key(run_id, rv["id"]), rv)
    return rv


def comment(store: Store, run_id: str, response_id: str, text: str) -> dict[str, Any]:
    key = _key(run_id, response_id)
    rv = feedback._read(store, key)
    if not rv:
        raise feedback.NotFound("unknown quick feedback")
    if rv["vote"] != "down":
        raise feedback.fb.FeedbackError("Optional comments belong to thumbs-down feedback.")
    rv.update(comment=text.strip(), updated_at=feedback.now())
    feedback._write(store, key, rv)
    return rv
