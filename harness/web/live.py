"""Live runs started from the console.

The agent runs locally with the console exporter writing one JSON span per line to out/<run>/live.jsonl; the
stream tails that file and turns each decision span into a timeline entry. After the agent ends: narrative,
report, then (judging.auto) the judge panel, whose progress is streamed too.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from analysis import timeline
from analysis.trace import Run
from core import geometry
from core.store import open_store
from harness import area as geo
from harness import config as config_mod
from harness import imagery, invoke
from harness.manifest import Index
from harness.tiles import settings as tiles_settings
from tools.lgnd import descriptors as lgnd
from tools.lgnd import results as lgnd_results


def archive_later(cfg: config_mod.Config, run: Run) -> threading.Thread:
    """Archive the run's result tiles in the background, after `done` is set, so the result isn't delayed."""
    from harness.cli import archive_tiles_quietly

    t = threading.Thread(
        target=archive_tiles_quietly, args=(cfg, run), name=f"tiles-{run.run_id}", daemon=True
    )
    t.start()
    return t


class RunState:
    def __init__(self, run_id: str, live: Path, serve_tiles: bool = True, archived: bool = False) -> None:
        self.run_id = run_id
        self.archived = archived  # a re-judge of an archived run: its tiles may already be in the archive
        self.serve_tiles = serve_tiles  # tiles.serve: result tiles through the console, else upstream
        self.live = live
        self.done = False
        self.area: geo.Area | None = None
        self.area_event: dict[str, Any] | None = None  # published only once complete
        self.extra: list[dict[str, Any]] = []  # judging events, in order
        self.final: dict[str, Any] | None = None
        self.lock = threading.Lock()

    def push(self, ev: dict[str, Any]) -> None:
        with self.lock:
            self.extra.append(ev)

    def annotate(self, chips: list[dict[str, Any]]) -> None:
        geom = self.area.geometry if self.area else None
        for c in chips:
            c["tile_url"] = (
                imagery.console_chip_url(c.get("index"), c["bbox"], self.run_id)
                if self.serve_tiles
                else imagery.tile_url(c.get("index"), c["bbox"])
            )
            c["tile_source"] = imagery.ATTRIBUTION.get(c.get("index") or "", imagery.ATTRIBUTION["s2"])
            if geom:
                try:
                    c["inside"] = geometry.contains(geom, float(c["lon"]), float(c["lat"]))
                except (TypeError, ValueError, KeyError):
                    pass


RUNS: dict[str, RunState] = {}


def span_event(span: dict[str, Any], state: RunState | None = None) -> dict[str, Any] | None:
    """One console-exported span line -> one stream event carrying a timeline entry (decision spans only)."""
    name, a = span.get("name", ""), span.get("attributes", {}) or {}
    ctx = span.get("context") or {}
    e = timeline.entry(name, a, ctx.get("span_id"), {"name": name, "attributes": a})
    if e is None:
        return None
    ev: dict[str, Any] = {"type": "step", "entry": e.as_dict()}
    if name == "harness.tool_result" and a.get("harness.tool.server") == lgnd.SERVER:
        extras = lgnd_results.extras(str(a.get("harness.tool.result") or ""))
        chips = extras.get("chips") or []
        for c in chips:
            c["ref"] = a.get("harness.tool.ref")
        if state is not None:
            state.annotate(chips)
        ev["chips"] = chips
        ev["entry"]["results"] = len(chips)
    return ev


def start_run(cfg: config_mod.Config, index: Index, prompt: str, model: str,
              on_done: Any = None) -> str:  # fmt: skip
    out = Path(cfg["out_dir"]) / "ui"
    out.mkdir(parents=True, exist_ok=True)
    prompt_file = out / f"prompt-{uuid.uuid4().hex[:8]}.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    plan = invoke.plan_run(cfg, prompt_file=str(prompt_file), model_key=model, backend="local")
    live = Path(cfg["out_dir"]) / plan.run_id / "live.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.touch()
    state = RunState(plan.run_id, live, serve_tiles=bool(tiles_settings(cfg)["serve"]))
    RUNS[plan.run_id] = state

    def work() -> None:
        from harness.cli import write_report
        from harness.web.view import run_view

        finished: Run | None = None

        env = {"HARNESS_EXPORTER": "console", "HARNESS_CONSOLE_PATH": str(live.resolve())}
        scripted = bool(os.environ.get("HARNESS_TEST_SCRIPT"))
        mode = str(cfg.get("area_mode") or "enforce")
        if not scripted and mode != "off":
            area, event = geo.area_for_prompt(cfg, prompt)
            invoke.attach_area(plan, geo.payload_area(area, mode))
            state.area = area
            if area is not None and area.geometry:
                event = {**event, "geometry": area.geometry}
            state.area_event = {**event, "mode": mode}
        else:
            state.area_event = {"type": "area", "label": None, "note": "No area check for this run."}
        try:
            outcome = invoke.execute(cfg, index, plan, extra_env=env)
            store = open_store(plan.archive_uri)
            run = Run.load(store, plan.run_id)
            if not scripted and run.all_spans:
                if cfg.get("narrative_model"):
                    from harness import narrative

                    model_id = cfg["models"][cfg["narrative_model"]]["id"]
                    narrative.write_summary(run, store, model_id, cfg["region"])
                from harness.conditions import ensure

                ensure(cfg, run)
                if (cfg.get("judging") or {}).get("auto"):
                    judge_into(cfg, state, run, store)
                run = Run.load(store, plan.run_id)
            write_report(cfg, run, archive_tiles=False)
            view = run_view(
                run,
                serve_tiles=state.serve_tiles,
                deploy_store=_deploy_or_none(cfg),
                reconsider=_reconsider(cfg),
                rubric_path=(cfg.get("judging") or {}).get("rubric"),
            )
            state.final = {"type": "done", "status": outcome.status, "error": outcome.error, "view": view}
            finished = run
        except Exception as e:  # noqa: BLE001 - shown on the page
            state.final = {"type": "done", "status": "error", "error": f"{type(e).__name__}: {e}"}
        finally:
            state.done = True
        if finished is not None:
            archive_later(cfg, finished)  # after `done`: tile archiving never delays the result

    threading.Thread(target=work, name=f"run-{plan.run_id}", daemon=True).start()
    return plan.run_id


def _deploy_or_none(cfg: config_mod.Config) -> Any:
    try:
        return open_store(cfg["archive_uri"])
    except Exception:  # noqa: BLE001 - the view works without reviews
        return None


def _reconsider(cfg: config_mod.Config) -> bool:
    return bool((cfg.get("judging") or {}).get("reconsider", True))


def judge_into(cfg: config_mod.Config, state: RunState, run: Run, store: Any) -> None:
    """Run the panel, streaming each judge's result as it lands."""
    from harness import judge

    try:
        judge.judge_run(cfg, run, store, on_event=state.push)
    except Exception as e:  # noqa: BLE001 - the run stands without a score
        state.push({"type": "judge_error", "error": f"{type(e).__name__}: {e}"})


def rejudge(cfg: config_mod.Config, index: Index, run_id: str) -> RunState:
    """Re-judge an archived run in the background; progress goes to the same event stream."""
    from harness.cli import write_report
    from harness.web.view import run_view

    uri = index.run_uri(run_id) or cfg["archive_uri"]
    store = open_store(uri)
    live = Path(cfg["out_dir"]) / run_id / "rejudge.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text("", encoding="utf-8")
    state = RunState(run_id, live, serve_tiles=bool(tiles_settings(cfg)["serve"]), archived=True)
    state.area_event = {"type": "rejudge"}
    RUNS[run_id] = state

    def work() -> None:
        finished: Run | None = None
        try:
            run = Run.load(store, run_id)
            judge_into(cfg, state, run, store)
            run = Run.load(store, run_id)
            write_report(cfg, run, archive_tiles=False)
            view = run_view(
                run,
                serve_tiles=state.serve_tiles,
                deploy_store=_deploy_or_none(cfg),
                reconsider=_reconsider(cfg),
                rubric_path=(cfg.get("judging") or {}).get("rubric"),
            )
            state.final = {"type": "done", "status": run.status, "error": None, "view": view}
            finished = run
        except Exception as e:  # noqa: BLE001
            state.final = {"type": "done", "status": "error", "error": f"{type(e).__name__}: {e}"}
        finally:
            state.done = True
        if finished is not None:
            archive_later(cfg, finished)  # after `done`: tile archiving never delays the result

    threading.Thread(target=work, name=f"judge-{run_id}", daemon=True).start()
    return state


def reconsider_job(cfg: config_mod.Config, index: Index, run_id: str, review_id: str) -> RunState:
    """The judges reconsider an archived run with a review, in the background (docs/judge-feedback AC3)."""
    from harness import feedback
    from harness.cli import write_report
    from harness.web.view import run_view

    store = open_store(index.run_uri(run_id) or cfg["archive_uri"])
    deploy = feedback.deployment_store(cfg)
    live = Path(cfg["out_dir"]) / run_id / "reconsider.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text("", encoding="utf-8")
    state = RunState(run_id, live, serve_tiles=bool(tiles_settings(cfg)["serve"]), archived=True)
    state.area_event = {"type": "reconsider", "review_id": review_id}
    RUNS[run_id] = state

    def work() -> None:
        try:
            feedback.reconsider(cfg, Run.load(store, run_id), store, deploy, review_id, on_event=state.push)
            run = Run.load(store, run_id)
            write_report(cfg, run, archive_tiles=False)
            state.final = {
                "type": "done",
                "status": run.status,
                "error": None,
                "view": run_view(
                    run,
                    serve_tiles=state.serve_tiles,
                    deploy_store=deploy,
                    reconsider=_reconsider(cfg),
                    rubric_path=(cfg.get("judging") or {}).get("rubric"),
                ),
            }
        except Exception as e:  # noqa: BLE001 - the judgement stays as it was
            state.final = {"type": "done", "status": "error", "error": f"{type(e).__name__}: {e}"}
        finally:
            state.done = True

    threading.Thread(target=work, name=f"reconsider-{run_id}", daemon=True).start()
    return state


GUIDANCE_JOBS: dict[int, RunState] = {}


def evaluate_job(cfg: config_mod.Config, index: Index, n: int) -> RunState:
    """Evaluate a guidance version in the background (docs/judge-feedback AC10)."""
    from harness import feedback

    live = Path(cfg["out_dir"]) / "guidance" / f"evaluate-{n}.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text("", encoding="utf-8")
    state = RunState(f"guidance-{n}", live, archived=True)
    state.area_event = {"type": "evaluating", "version": n}
    GUIDANCE_JOBS[n] = state

    def work() -> None:
        try:
            rep = feedback.evaluate(cfg, feedback.deployment_store(cfg), index, n, on_event=state.push)
            state.final = {"type": "done", "status": rep["verdict"], "error": None, "report": rep}
        except Exception as e:  # noqa: BLE001 - nothing is stored on failure
            state.final = {"type": "done", "status": "error", "error": f"{type(e).__name__}: {e}"}
        finally:
            state.done = True

    threading.Thread(target=work, name=f"evaluate-{n}", daemon=True).start()
    return state


def read_new(state: RunState, pos: int) -> tuple[list[dict[str, Any]], int]:
    with state.live.open("r", encoding="utf-8") as f:
        f.seek(pos)
        chunk = f.read()
        pos = f.tell()
    events = []
    for line in chunk.splitlines():
        try:
            ev = span_event(json.loads(line), state)
        except json.JSONDecodeError:
            continue
        if ev:
            events.append(ev)
    return events, pos
