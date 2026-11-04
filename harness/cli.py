"""`harness` command line (design: Experience). Slice 1: check, replay, compare (archive-only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from analysis import check, report
from analysis.store import Store, open_store
from analysis.trace import ArchiveError, Run
from harness import config as config_mod
from harness import invoke
from harness.manifest import Index


def _now() -> str:
    return os.environ.get("HARNESS_GENERATED_AT") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_store(cfg: config_mod.Config, index: Index, run_id: str) -> Store:
    return open_store(index.run_uri(run_id) or cfg["archive_uri"])


def cmd_check(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    run = Run.load(_run_store(cfg, index, args.run_id), args.run_id)
    missing = check.check_run(run)
    if not missing:
        print(f"{args.run_id}: 0 missing fields")
        return 0
    print(f"{args.run_id}: {len(missing)} missing fields:")
    for m in missing:
        print(m.line())
    return 1


def write_report(cfg: config_mod.Config, run: Run) -> Path:
    out = Path(cfg["out_dir"]) / run.run_id
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.html"
    path.write_text(report.render_run(report.analyze(run), _now()), encoding="utf-8")
    return path


def cmd_replay(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    run = Run.load(_run_store(cfg, index, args.run_id), args.run_id)
    path = write_report(cfg, run)
    print(f"replayed {args.run_id} → {path}")
    return 0


def cmd_compare(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    uri = index.suite_uri(args.suite_id) or cfg["archive_uri"]
    store = open_store(uri)
    text = store.read_text(f"suites/{args.suite_id}/suite.json")
    if text is None:
        print(f"no suite manifest at {uri}/suites/{args.suite_id}/suite.json.")
        return 1
    suite = json.loads(text)
    if not suite.get("run_ids"):
        print(f"suite {args.suite_id} has no archived runs.")
        return 1
    reports = []
    for run_id in suite["run_ids"]:
        try:
            reports.append(report.analyze(Run.load(open_store(index.run_uri(run_id) or uri), run_id)))
        except ArchiveError as e:
            print(f"warning: {e}", file=sys.stderr)
    rows = report.compare_rows(reports)
    out = Path(cfg["out_dir"]) / args.suite_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.html").write_text(report.render_compare(args.suite_id, rows, _now()), encoding="utf-8")
    (out / "compare.csv").write_text(report.compare_csv(rows), encoding="utf-8")
    print(f"→ {out / 'compare.html'} ({len(rows)} rows), compare.csv")
    return 0


def cmd_run(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    backend = args.backend or cfg["backend"]
    model_key = args.model or next(iter(cfg["models"]), None)
    try:
        plan = invoke.plan_run(cfg, prompt_file=args.prompt, model_key=model_key, backend=backend)
    except invoke.RunRefused as e:
        print(str(e))
        return 2
    print(f"worst case for this run: ${plan.worst_case_usd:.2f}")
    outcome = invoke.execute(cfg, index, plan)
    run = Run.load(open_store(plan.archive_uri), plan.run_id)
    path = write_report(cfg, run)
    rep = report.analyze(run)
    c = rep.prov.counts()
    if outcome.status in ("ok", "limit_exceeded"):
        print(
            f"run {plan.run_id} done: {rep.sig.steps} steps, {rep.sig.errors} errors, "
            f"claims {c['matched']} matched / {c['mismatch']} mismatch / {c['unsourced']} unsourced → {path}"
            + (f" (status {outcome.status}: {outcome.error})" if outcome.status != "ok" else "")
        )
        return 0
    print(
        f"run {plan.run_id} failed: {outcome.error}. Partial trace archived; "
        f"run 'harness replay {plan.run_id}' to see what happened."
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="Track 1 evaluation harness")
    p.add_argument("--config", default=None, help="path to harness.yaml (default: ./harness.yaml)")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the agent on a prompt and report it")
    run.add_argument("--prompt", required=True, help="prompt file, e.g. prompts/dallas-dc.md")
    run.add_argument("--model", default=None, help="model key from harness.yaml models")
    run.add_argument("--backend", choices=["agentcore", "local"], default=None)
    c = sub.add_parser("check", help="run the AC2 trace checker on an archived run")
    c.add_argument("run_id")
    r = sub.add_parser("replay", help="rebuild a run's report from the archive only")
    r.add_argument("run_id")
    k = sub.add_parser("compare", help="build the comparison table for a suite")
    k.add_argument("suite_id")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_mod.load(args.config)
        index = Index(cfg["out_dir"])
        handler = {"run": cmd_run, "check": cmd_check, "replay": cmd_replay, "compare": cmd_compare}[
            args.command
        ]
        return handler(cfg, index, args)
    except (ArchiveError, FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
