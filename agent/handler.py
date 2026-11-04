"""handle(payload) -> response: one agent run (design: Invocation contract, Agent internals).

Shared by the AgentCore HTTP route (agent/main.py) and the local runner (agent/local.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from agent import runctx
from agent.hooks import HarnessHooks, LimitExceeded
from agent.telemetry import flush_exporters, setup
from core import prompts
from tools import registry

log = logging.getLogger("harness.agent")
REQUIRED = ("schema_version", "run_id", "prompt", "prompt_sha256", "model_id", "model_params", "limits")
CANCEL_GRACE_S = 180


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"


def _validate(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "bad payload: not an object"
    if payload.get("schema_version") != 1:
        return "bad payload: schema_version"
    for f in REQUIRED:
        if f not in payload:
            return f"bad payload: {f}"
    return None


def _bedrock_model(payload: dict[str, Any]) -> Any:
    from botocore.config import Config
    from strands.models.bedrock import BedrockModel

    params = payload["model_params"]
    return BedrockModel(
        model_id=payload["model_id"],
        region_name=_region(),
        max_tokens=int(params.get("max_tokens", 16000)),
        additional_request_fields=params.get("request_fields") or {},
        boto_client_config=Config(
            connect_timeout=10, read_timeout=120, retries={"mode": "standard", "max_attempts": 3}
        ),
    )


def _scripted(path: str) -> tuple[Any, list[Any], dict[str, str], list[dict[str, Any]]]:
    from tools.scripted import ScriptedModel, lookup_facility

    turns = json.loads(Path(path).read_text(encoding="utf-8"))
    available = [{"server": "local", "tool": "lookup_facility", "input_schema": {}}]
    return ScriptedModel(turns), [lookup_facility], {"lookup_facility": "local"}, available


def handle(payload: Any) -> dict[str, Any]:
    error = _validate(payload)
    run_id = payload.get("run_id", "unknown") if isinstance(payload, dict) else "unknown"
    base = {"schema_version": 1, "run_id": run_id, "final_output": "", "tool_refs": {}, "archive_errors": 0}
    if error:
        return {**base, "status": "error", "error": error}

    from strands import Agent
    from strands.agent.conversation_manager import NullConversationManager

    tel = setup()
    system_prompt = prompts.load("agent/system")
    runctx.set_context(
        {
            "run_id": run_id,
            "suite_id": payload.get("suite_id"),
            "prompt_sha256": payload["prompt_sha256"],
            "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
            "model_id": payload["model_id"],
            "model_params_json": json.dumps(payload["model_params"], sort_keys=True),
            "ended": False,
        }
    )
    tel.archive.start_run()
    limits = {
        "max_tokens": int(payload["model_params"].get("max_tokens", 16000)),
        "model_id": payload["model_id"],
        **payload["limits"],
    }
    limits.setdefault("max_output_tokens", 200_000)
    status, err, final_output = "error", None, ""
    hooks: HarnessHooks | None = None
    with ExitStack() as stack:
        try:
            script = os.environ.get("HARNESS_TEST_SCRIPT")
            if script:
                model, tools, server_of, available = _scripted(script)
            else:
                model = _bedrock_model(payload)
                tools, server_of, available = registry.build(
                    stack,
                    timeout_s=int(limits.get("tool_timeout_s", 60)),
                    region=_region(),
                    lgnd_url=os.environ.get("HARNESS_LGND_URL"),
                    lgnd_secret_id=os.environ.get("HARNESS_LGND_SECRET_ID"),
                )
            search_area = payload.get("search_area")
            hooks = HarnessHooks(
                tracer=tel.tracer(),
                writer=tel.writer,
                run_id=run_id,
                tools_available=available,
                limits=limits,
                server_of=server_of,
                search_area=search_area,
            )
            hooks.run_start()
            run_system_prompt = system_prompt
            if search_area and search_area.get("label"):
                label, source = search_area["label"], search_area.get("source")
                run_system_prompt += (
                    "\n\n" + prompts.load("agent/search_area", label=label, source=source).strip()
                )
                if search_area.get("mode") == "enforce" and search_area.get("lgnd_area"):
                    run_system_prompt += " " + prompts.load("agent/search_area_enforced").strip()
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=run_system_prompt,
                hooks=[hooks],
                conversation_manager=NullConversationManager(),
                callback_handler=None,
            )
            box: dict[str, Any] = {}

            def work() -> None:
                try:
                    box["result"] = agent(payload["prompt"])
                except BaseException as e:  # noqa: BLE001 - reported as the run's status
                    box["exc"] = e

            worker = threading.Thread(target=work, name="harness-agent", daemon=True)
            worker.start()
            worker.join(timeout=float(limits.get("wall_clock_s", 600)))
            if worker.is_alive():
                hooks.cancel.set()  # cooperative: the next model or tool call raises LimitExceeded
                worker.join(timeout=CANCEL_GRACE_S)
                status, err = "limit_exceeded", "wall clock exceeded"
            elif hooks.limit_reason or isinstance(box.get("exc"), LimitExceeded):
                # Strands wraps a hook's exception in EventLoopException, so trust the hooks' own record.
                status, err = "limit_exceeded", hooks.limit_reason or str(box["exc"])
            elif "exc" in box:
                status, err = "error", f"{type(box['exc']).__name__}: {box['exc']}"
            else:
                status, final_output = "ok", str(box["result"])
                stop = getattr(box["result"], "stop_reason", None)
                if str(stop) == "max_tokens":
                    status, err = "error", "final answer truncated at max_tokens"
        except Exception as e:  # noqa: BLE001 - setup failures (tool server, model) end the run
            status, err = "error", f"{type(e).__name__}: {e}"
            log.exception("run %s failed", run_id)
        finally:
            if hooks is not None:
                hooks.run_end(status, tel.writer.errors)
            runctx.update(ended=True)
            tel.archive.force_flush()
            flush_exporters()
    response = {
        **base,
        "status": status,
        "error": err,
        "final_output": final_output,
        "tool_refs": hooks.refs if hooks else {},
        "archive_errors": tel.writer.errors,
    }
    tel.writer.put(f"runs/{run_id}/result.json", json.dumps(response))
    tel.writer.wait(60)
    return response
