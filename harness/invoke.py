"""Plan and execute one run: payload, cost guard, run.json, local subprocess or AgentCore invoke."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analysis.store import open_store
from harness.config import Config
from harness.manifest import Index

DEFAULT_LIMITS = {"max_steps": 40, "max_input_tokens": 400_000, "max_output_tokens": 200_000,
                  "wall_clock_s": 600, "tool_timeout_s": 60}  # fmt: skip
NARRATIVE_IN_MTOK, NARRATIVE_OUT_MTOK = 0.05, 0.002


class RunRefused(Exception):
    pass


@dataclass
class RunPlan:
    run_id: str
    suite_id: str | None
    backend: str
    model_key: str
    archive_uri: str
    payload: dict[str, Any]
    manifest: dict[str, Any]
    worst_case_usd: float


@dataclass
class Outcome:
    status: str
    error: str | None


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _price(cfg: Config, key: str) -> dict[str, float]:
    p = (cfg["prices_per_mtok"] or {}).get(key)
    if not isinstance(p, dict) or not all(isinstance(p.get(k), int | float) for k in ("in", "out")):
        raise RunRefused(f"prices_per_mtok.{key} is not set; fill it from the Bedrock pricing page.")
    return {"in": float(p["in"]), "out": float(p["out"])}


def worst_case_usd(cfg: Config, model_key: str) -> float:
    p = _price(cfg, model_key)
    lim = DEFAULT_LIMITS
    usd = lim["max_input_tokens"] / 1e6 * p["in"] + lim["max_output_tokens"] / 1e6 * p["out"]
    narrative = cfg.get("narrative_model")
    if narrative:
        n = _price(cfg, narrative)
        usd += NARRATIVE_IN_MTOK * n["in"] + NARRATIVE_OUT_MTOK * n["out"]
    return usd


def plan_run(
    cfg: Config, *, prompt_file: str, model_key: str | None, backend: str, suite_id: str | None = None
) -> RunPlan:
    models = cfg["models"] or {}
    if not model_key or model_key not in models:
        raise RunRefused(f"unknown model key {model_key!r} (known: {', '.join(models) or 'none'}).")
    path = Path(prompt_file)
    if not path.is_file():
        raise RunRefused(f"prompt file {prompt_file} not found.")
    if backend == "agentcore" and not cfg.get("runtime_arn"):
        raise RunRefused(
            "runtime_arn is not set in harness.yaml; deploy with CDK first or use --backend local."
        )
    usd = worst_case_usd(cfg, model_key)
    prompt = path.read_text(encoding="utf-8")
    m = models[model_key]
    run_id = str(uuid.uuid4())
    archive_uri = cfg["local_archive_uri"] if backend == "local" else cfg["archive_uri"]
    model_params = {
        "max_tokens": int(m.get("max_tokens", 16000)),
        "request_fields": m.get("request_fields") or {},
    }
    sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    payload = {"schema_version": 1, "run_id": run_id, "suite_id": suite_id, "prompt": prompt,
               "prompt_file": prompt_file, "prompt_sha256": sha, "model_id": m["id"],
               "model_params": model_params, "limits": DEFAULT_LIMITS}  # fmt: skip
    manifest = {"schema_version": 1, "run_id": run_id, "suite_id": suite_id, "backend": backend,
                "model_key": model_key, "model_id": m["id"], "prompt_file": prompt_file, "prompt_sha256": sha,
                "started_at": _now(), "ended_at": None, "status": "running", "final_output": "",
                "archive_uri": archive_uri, "archive_errors": 0,
                "snapshot": {"prices_per_mtok": cfg["prices_per_mtok"], "rubric": _rubric(cfg),
                             "scorer": cfg["scorer"], "harness_version": _git_sha()}}  # fmt: skip
    return RunPlan(run_id, suite_id, backend, model_key, archive_uri, payload, manifest, usd)


def _rubric(cfg: Config) -> Any:
    path = cfg.get("rubric")
    if not path:
        return None
    import yaml

    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def attach_area(plan: RunPlan, search_area: dict[str, Any] | None) -> None:
    """Send the prompt's area to the agent and snapshot it in run.json (replay never re-resolves it)."""
    if search_area is None:
        return
    plan.payload["search_area"] = {k: v for k, v in search_area.items() if k != "geometry"}
    plan.manifest["snapshot"]["search_area"] = search_area


def execute(cfg: Config, index: Index, plan: RunPlan, extra_env: dict[str, str] | None = None) -> Outcome:
    store = open_store(plan.archive_uri)
    key = f"runs/{plan.run_id}/run.json"
    store.write_text(key, json.dumps(plan.manifest, indent=1))
    index.record_run(plan.run_id, plan.archive_uri)
    try:
        result = _run_local(cfg, plan, extra_env) if plan.backend == "local" else _run_agentcore(cfg, plan)
    except Exception as e:  # noqa: BLE001 - recorded in run.json, never retried automatically
        result = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    if result.get("status") != "error" or "final_output" not in result:
        archived = store.read_text(f"runs/{plan.run_id}/result.json")
        if archived:
            result = {**json.loads(archived), **({"error": result["error"]} if result.get("error") else {})}
    manifest = {**plan.manifest, "ended_at": _now(), "status": result.get("status", "error"),
                "final_output": result.get("final_output", ""),
                "archive_errors": int(result.get("archive_errors", 0) or 0)}  # fmt: skip
    store.write_text(key, json.dumps(manifest, indent=1))
    return Outcome(str(manifest["status"]), result.get("error"))


def _run_local(cfg: Config, plan: RunPlan, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    out = Path(cfg["out_dir"]) / plan.run_id
    out.mkdir(parents=True, exist_ok=True)
    payload_path = out / "payload.json"
    payload_path.write_text(json.dumps(plan.payload), encoding="utf-8")
    env = {**os.environ, "HARNESS_ARCHIVE_URI": plan.archive_uri,
           "HARNESS_EXPORTER": os.environ.get("HARNESS_EXPORTER", cfg["local_exporter"])}  # fmt: skip
    if cfg.get("lgnd_secret_id") and not os.environ.get("HARNESS_TEST_SCRIPT"):
        # same LGND Geo access as the deployed runtime (refresh token in Secrets Manager)
        env.setdefault("HARNESS_LGND_URL", "https://geo.lgnd.ai/mcp")
        env.setdefault("HARNESS_LGND_SECRET_ID", str(cfg["lgnd_secret_id"]))
    env.update(extra_env or {})
    proc = subprocess.run([sys.executable, "-m", "agent.local", str(payload_path)], env=env, timeout=900,
                          capture_output=True, text=True)  # fmt: skip
    (out / "agent.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        return {
            "status": "error",
            "error": f"local agent crashed (exit {proc.returncode}); see {out / 'agent.log'}",
        }
    return {"status": "ok"}


def _run_agentcore(cfg: Config, plan: RunPlan) -> dict[str, Any]:
    import boto3
    from botocore.config import Config as BotoConfig

    client = boto3.client(
        "bedrock-agentcore",
        region_name=cfg["region"],
        config=BotoConfig(read_timeout=900, connect_timeout=10, retries={"max_attempts": 1}),
    )
    for attempt, delay in enumerate((0, 1, 2, 4)):
        time.sleep(delay)
        try:
            resp = client.invoke_agent_runtime(
                agentRuntimeArn=cfg["runtime_arn"],
                runtimeSessionId=plan.run_id,
                payload=json.dumps(plan.payload),
            )
            body = resp["response"].read()
            result: dict[str, Any] = json.loads(body)
            return result
        except client.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code == "RetryableConflictException" and attempt < 3:
                continue  # the session is still being provisioned; the agent hasn't started
            raise
    raise RuntimeError("unreachable")
