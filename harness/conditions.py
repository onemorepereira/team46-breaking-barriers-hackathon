"""Archive request conditions; explicit re-judging retries failed extraction, replay stays offline."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from analysis.trace import Run
from core import prompts


def validate(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("conditions"), list) or not data["conditions"]:
        raise ValueError("condition extraction returned no conditions")
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
            if not cached.get("error") and cached.get("conditions"):
                validate(cached)
                return
        except (ValueError, AttributeError):
            pass
    saved: dict[str, Any] = {"schema_version": 1, "conditions": []}
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
                proximity = re.search(
                    r"\b(?:within|less than|up to|no more than|near)\s+(?:about\s+)?"
                    r"\d+(?:\.\d+)?\s*(?:miles?|km|kilomet(?:er|re)s?)\s+"
                    r"(?:of|from)\b",
                    run.prompt,
                    re.I,
                )
                if proximity and not any(c["kind"] == "within_distance" for c in extracted):
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
