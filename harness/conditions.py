"""Archive request conditions; explicit re-judging retries failed extraction, replay stays offline."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from analysis.trace import Run
from core import prompts

_NUM = r"\d+(?:\.\d+)?"
_UNIT = r"(?:mi|miles?|kms?|kilomet(?:er|re)s?)\b"
_FILLER = r"(?:(?:a|an|about|around|approximately|roughly)\s+)*"
# A distance that sets a minimum isn't a "within" condition.
_MINIMUM = re.compile(
    rf"\b(?:more than|greater than|at least|over|beyond|further than|farther than|outside)\s+{_FILLER}"
    rf"{_NUM}[\s-]*{_UNIT}",
    re.I,
)
_PROXIMITY = re.compile(
    rf"\b(?:within|less than|under|up to|no more than|at most|closer than|no further than|no farther than"
    rf"|near)\s+{_FILLER}{_NUM}[\s-]*{_UNIT}(?:\s+(?:radius|buffer))?\s+(?:of|from|to|around)\b"
    rf"|\b{_NUM}[\s-]*{_UNIT}\s+(?:radius|buffer)\s+(?:of|from|around)\b"
    rf"|\b{_NUM}[\s-]*{_UNIT}\s+from\b",
    re.I,
)


def proximity_phrases(prompt: str) -> int:
    """How many distinct proximity limits the request states: a safety net under the model."""
    text = _MINIMUM.sub(" ", prompt)
    # Keyed with the feature's first word: a restated limit counts once, limits on two features twice.
    limits = set()
    for m in _PROXIMITY.finditer(text):
        feature = re.match(r"\s+(?:(?:a|an|the)\s+)?(\w+)", text[m.end() :])
        limits.add((m.group(0).lower(), feature.group(1).lower() if feature else ""))
    return len(limits)


def validate(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("conditions"), list):
        raise ValueError("condition extraction returned no conditions list")
    out = []
    for i, raw in enumerate(data["conditions"]):
        if not isinstance(raw, dict):
            raise ValueError("condition must be an object")
        kind = raw.get("kind")
        if kind not in ("target", "inside_area", "within_distance", "other"):
            raise ValueError("unknown condition kind")
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("condition text missing")
        c = {"id": f"C{i + 1}", "kind": kind, "text": text.strip()}
        if kind == "within_distance":
            km = raw.get("distance_km")
            feature = raw.get("reference_feature")
            if isinstance(km, bool) or not isinstance(km, int | float) or not math.isfinite(km) or km <= 0:
                raise ValueError("invalid distance")
            if not isinstance(feature, str) or not feature.strip():
                raise ValueError("reference feature missing")
            c.update(distance_km=km, reference_feature=feature.strip())
        out.append(c)
    return out


def ensure(cfg: Any, run: Run, client: Any = None) -> None:
    key = f"runs/{run.run_id}/conditions.json"
    previous = run.store.read_text(key)
    if previous:
        try:
            cached = json.loads(previous)
            if not cached.get("error") and cached.get("status") != "not_checked":
                validate(cached)
                return
        except (ValueError, AttributeError):
            pass
    saved: dict[str, Any] = {"schema_version": 1, "conditions": []}
    if not (run.prompt or "").strip():
        # No saved request means nothing to extract, which isn't a failure.
        run.store.write_text(key, json.dumps(saved))
        return
    try:
        model = cfg.get("narrative_model")
        if not model:
            # Optional feature: default configurations can still judge the rest of the rubric.
            saved["status"] = "not_checked"
            run.store.write_text(key, json.dumps(saved))
            return
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=cfg["region"],
                config=Config(connect_timeout=10, read_timeout=60),
            )
        messages = [{"role": "user", "content": [{"text": run.prompt}]}]
        usage: dict[str, int] = {}
        for attempt in range(2):
            reply = client.converse(
                modelId=cfg["models"][model]["id"],
                system=[{"text": prompts.load("harness/conditions_extract")}],
                messages=messages,
                inferenceConfig={"maxTokens": 1500},
            )
            for name, value in reply.get("usage", {}).items():
                usage[name] = usage.get(name, 0) + value
            saved.update(usage=usage, model_id=cfg["models"][model]["id"], attempts=attempt + 1)
            text = "".join(b.get("text", "") for b in reply["output"]["message"]["content"])
            try:
                # Decode an object even when surrounded by Markdown fences or explanatory prose.
                start = text.find("{")
                if start < 0:
                    raise ValueError("no JSON object in reply")
                data, _ = json.JSONDecoder().raw_decode(text[start:])
                extracted = validate(data)
                found = sum(c["kind"] == "within_distance" for c in extracted)
                if found < proximity_phrases(run.prompt):
                    raise ValueError("Distance condition omitted by extraction")
                saved["conditions"] = extracted
                break
            except ValueError as error:
                if attempt:
                    raise
                messages += [
                    {"role": "assistant", "content": [{"text": text or "(empty)"}]},
                    {
                        "role": "user",
                        "content": [{"text": prompts.load("harness/conditions_retry", error=error).strip()}],
                    },
                ]
    except Exception as e:
        saved["error"] = f"Condition extraction unavailable: {type(e).__name__}"
    run.store.write_text(key, json.dumps(saved))
