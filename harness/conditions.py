"""Extract once for new runs; never invoked by replay or re-judging."""

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
    if run.store.read_text(key) is not None:
        return
    saved: dict[str, Any] = {"schema_version": 1, "conditions": []}
    try:
        model = cfg.get("narrative_model")
        if not model:
            raise ValueError("No condition extraction model configured")
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=cfg["region"],
                config=Config(connect_timeout=10, read_timeout=60),
            )
        reply = client.converse(
            modelId=cfg["models"][model]["id"],
            system=[{"text": prompts.load("harness/conditions_extract")}],
            messages=[{"role": "user", "content": [{"text": run.prompt}]}],
            inferenceConfig={"maxTokens": 1500},
        )
        text = "".join(b.get("text", "") for b in reply["output"]["message"]["content"])
        saved["conditions"] = validate(json.loads(text))
        if re.search(r"\b\d+(?:\.\d+)?\s*(?:miles?|km|kilomet(?:er|re)s?)\b", run.prompt, re.I):
            if not any(c["kind"] == "within_distance" for c in saved["conditions"]):
                raise ValueError("Distance condition omitted by extraction")
        saved["usage"] = reply.get("usage", {})
        saved["model_id"] = cfg["models"][model]["id"]
    except Exception as e:
        saved["error"] = f"Condition extraction unavailable: {type(e).__name__}"
    run.store.write_text(key, json.dumps(saved))
