"""`harness` command line (design: Experience). Slice 1: check, replay, compare (archive-only)."""

from __future__ import annotations

import argparse
import hashlib
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


def _run_one(cfg: config_mod.Config, index: Index, plan: invoke.RunPlan) -> tuple[invoke.Outcome, str]:
    outcome = invoke.execute(cfg, index, plan)
    store = open_store(plan.archive_uri)
    run = Run.load(store, plan.run_id)
    narrative_key = cfg.get("narrative_model")
    if narrative_key and not os.environ.get("HARNESS_TEST_SCRIPT") and run.all_spans:
        from harness import narrative

        model_id = cfg["models"][narrative_key]["id"]
        if narrative.write_summary(run, store, model_id, cfg["region"]) is None:
            print(
                f"run {plan.run_id}: narrative unavailable (the report has the full timeline)",
                file=sys.stderr,
            )
        run = Run.load(store, plan.run_id)
    path = write_report(cfg, run)
    rep = report.analyze(run)
    c = rep.prov.counts()
    if outcome.status in ("ok", "limit_exceeded"):
        line = (
            f"run {plan.run_id} done: {rep.sig.steps} steps, {rep.sig.errors} errors, "
            f"claims {c['matched']} matched / {c['mismatch']} mismatch / {c['unsourced']} unsourced → {path}"
        )
        if outcome.status != "ok":
            line += f" (status {outcome.status}: {outcome.error})"
    else:
        line = (
            f"run {plan.run_id} failed: {outcome.error}. Partial trace archived; "
            f"run 'harness replay {plan.run_id}' to see what happened."
        )
    return outcome, line


def cmd_run(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    backend = args.backend or cfg["backend"]
    if args.suite:
        return cmd_suite(cfg, index, args, backend)
    model_key = args.model or next(iter(cfg["models"]), None)
    try:
        plan = invoke.plan_run(cfg, prompt_file=args.prompt, model_key=model_key, backend=backend)
    except invoke.RunRefused as e:
        print(str(e))
        return 2
    print(f"worst case for this run: ${plan.worst_case_usd:.2f}")
    outcome, line = _run_one(cfg, index, plan)
    print(line)
    return 0 if outcome.status in ("ok", "limit_exceeded") else 1


def cmd_suite(cfg: config_mod.Config, index: Index, args: argparse.Namespace, backend: str) -> int:
    import yaml

    spec = yaml.safe_load(Path(args.suite).read_text(encoding="utf-8")) or {}
    name, prompts, models = spec.get("suite"), spec.get("prompts") or [], spec.get("models") or []
    backend = args.backend or spec.get("backend") or backend
    if not name or not prompts or not models:
        print(f"suite file {args.suite}: needs suite, prompts and models.")
        return 2
    known = cfg["models"] or {}
    for m in models:
        if m not in known:
            print(f"suite {name}: unknown model key {m!r} (known: {', '.join(known)}).")
            return 2
    for pf in prompts:
        if not Path(pf).is_file():
            print(f"suite {name}: prompt file {pf} not found.")
            return 2
    total = len(prompts) * len(models)
    if total > int(cfg["max_runs_per_suite"]):
        print(
            f"suite has {total} runs; max_runs_per_suite is {cfg['max_runs_per_suite']}. "
            "Shrink the suite or raise the limit in harness.yaml."
        )
        return 2
    try:
        worst = sum(invoke.worst_case_usd(cfg, m) for _ in prompts for m in models)
    except invoke.RunRefused as e:
        print(str(e))
        return 2
    if worst > float(cfg["max_suite_usd"]):
        print(
            f"suite worst case ${worst:.2f} exceeds max_suite_usd ${float(cfg['max_suite_usd']):.0f}. "
            "Shrink the suite or raise max_suite_usd in harness.yaml."
        )
        return 2
    suite_id = f"{name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M')}"
    archive_uri = cfg["local_archive_uri"] if backend == "local" else cfg["archive_uri"]
    store = open_store(archive_uri)
    sha = hashlib.sha256(Path(args.suite).read_bytes()).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "suite_id": suite_id,
        "suite_file_sha256": sha,
        "run_ids": [],
    }
    store.write_text(f"suites/{suite_id}/suite.json", json.dumps(manifest, indent=1))
    index.record_suite(suite_id, archive_uri)
    print(f"suite {suite_id}: {total} runs, worst case ${worst:.2f}")
    ok, failed = 0, []
    for pf in prompts:  # prompt-major order
        for m in models:
            plan = invoke.plan_run(cfg, prompt_file=pf, model_key=m, backend=backend, suite_id=suite_id)
            outcome, line = _run_one(cfg, index, plan)
            print(line)
            run_ids = manifest["run_ids"]
            assert isinstance(run_ids, list)
            run_ids.append(plan.run_id)
            store.write_text(f"suites/{suite_id}/suite.json", json.dumps(manifest, indent=1))
            if outcome.status in ("ok", "limit_exceeded"):
                ok += 1
            else:
                failed.append(f"run {plan.run_id}: {outcome.error}")
    if failed:
        print(f"suite {suite_id} done: {ok}/{total} runs ok, {len(failed)} failed ({'; '.join(failed)})")
    else:
        print(f"suite {suite_id} done: {total}/{total} runs → harness compare {suite_id}")
    return 0 if not failed else 1


def cmd_lgnd_login(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import lgnd

    secret = args.secret or cfg.get("lgnd_secret_id")
    if not secret:
        print("lgnd_secret_id is not set in harness.yaml; deploy with CDK first (output LgndSecretArn).")
        return 2
    if args.device:
        return lgnd.login_device(secret, cfg["region"])
    return lgnd.login_browser(secret, cfg["region"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="Track 1 evaluation harness")
    p.add_argument("--config", default=None, help="path to harness.yaml (default: ./harness.yaml)")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the agent on a prompt and report it")
    what = run.add_mutually_exclusive_group(required=True)
    what.add_argument("--prompt", help="prompt file, e.g. prompts/dallas-dc.md")
    what.add_argument("--suite", help="suite file, e.g. suites/dallas-dc-v1.yaml")
    run.add_argument("--model", default=None, help="model key from harness.yaml models")
    run.add_argument("--backend", choices=["agentcore", "local"], default=None)
    lg = sub.add_parser(
        "lgnd-login", help="one-time OAuth device login to LGND Geo; saves to Secrets Manager"
    )
    lg.add_argument("--secret", default=None, help="secret ID (default: lgnd_secret_id in harness.yaml)")
    lg.add_argument("--device", action="store_true", help="use the device-code flow instead of the browser")
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
        handler = {
            "run": cmd_run,
            "check": cmd_check,
            "replay": cmd_replay,
            "compare": cmd_compare,
            "lgnd-login": cmd_lgnd_login,
        }[args.command]
        return handler(cfg, index, args)
    except (ArchiveError, FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
