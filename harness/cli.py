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
from analysis.trace import ArchiveError, Run
from core.store import Store, open_store
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
    from analysis.judging import panel

    judged = [rep.judgement for rep in reports if rep.judgement]
    agreement = panel.corpus_alpha(judged) if judged else None
    html = report.render_compare(args.suite_id, rows, _now(), agreement)
    (out / "compare.html").write_text(html, encoding="utf-8")
    (out / "compare.csv").write_text(report.compare_csv(rows), encoding="utf-8")
    print(f"→ {out / 'compare.html'} ({len(rows)} rows), compare.csv")
    return 0


def _run_one(cfg: config_mod.Config, index: Index, plan: invoke.RunPlan) -> tuple[invoke.Outcome, str]:
    mode = str(cfg.get("area_mode") or "enforce")
    if mode != "off" and not os.environ.get("HARNESS_TEST_SCRIPT"):
        from harness import area as geo

        area, event = geo.area_for_prompt(cfg, plan.payload["prompt"])
        invoke.attach_area(plan, geo.payload_area(area, mode))
        print(f"area: {event.get('label') or '—'} ({event.get('source') or event.get('note')}; {mode})")
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
    if (cfg.get("judging") or {}).get("auto") and not os.environ.get("HARNESS_TEST_SCRIPT") and run.all_spans:
        from harness import judge

        try:
            judge.judge_run(cfg, run, store, on_event=_print_judge)
            run = Run.load(store, plan.run_id)
        except Exception as e:  # noqa: BLE001 - the run and its report stand without a score
            print(
                f"run {plan.run_id}: judging failed ({e}); run 'harness judge {plan.run_id}'", file=sys.stderr
            )
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


def cmd_judge(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import judge

    store = _run_store(cfg, index, args.run_id)
    run = Run.load(store, args.run_id)
    jd = judge.judge_run(cfg, run, store, passes=args.passes, on_event=_print_judge)
    write_report(cfg, Run.load(store, args.run_id))
    p = jd["panel"]
    print(
        f"{args.run_id}: {p['verdict']} overall {p['overall']} (workflow {p['dimensions']['workflow']}, "
        f"output {p['dimensions']['output']}), confidence {p['confidence']}, "
        f"judging ${jd['judging_cost_usd']:.3f}"
    )
    return 0 if p["status"] == "scored" else 1


def _print_judge(ev: dict[str, object]) -> None:
    if ev.get("type") == "judging":
        seats = ev.get("seats") or []
        assert isinstance(seats, list)
        names = [
            f"{s['key']}" + (f" (for {s['recused_for']})" if s.get("recused_for") else "") for s in seats
        ]
        print(f"panel: {', '.join(names)}; passes {ev.get('passes')}")
    elif ev.get("type") == "judge":
        tail = f"{ev.get('score')}" if ev.get("status") == "ok" else f"failed: {ev.get('error')}"
        print(f"  pass {ev.get('pass')} {ev.get('key')}: {tail} ({ev.get('latency_s')} s)")


def cmd_calibrate(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import calibrate

    store = _run_store(cfg, index, args.run_id)
    out = calibrate.calibrate(cfg, Run.load(store, args.run_id), store, passes=args.passes)
    print(f"calibration of {args.run_id} (panel: {', '.join(out['seats'])}; passes {out['passes']}):")
    for r in out["rows"]:
        if r["verdict"] == "skipped":
            print(f"  {r['perturbation']:<11} skipped (no target in the rubric)")
            continue
        flag = "  non-specific" if r.get("non_specific") else ""
        print(
            f"  {r['perturbation']:<11} → {r['target']:<20} {r['original']} → {r['perturbed']} "
            f"(drop {r['drop']}, largest other drop {r['max_other_drop']}): {r['verdict']}{flag}"
        )
    print(f"cost ${out['cost_usd']:.3f} → runs/{args.run_id}/calibration.json")
    return int(out["exit_code"])


def cmd_agreement(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from analysis.judging import panel

    ids = list(args.run_ids)
    if args.suite:
        uri = index.suite_uri(args.suite) or cfg["archive_uri"]
        text = open_store(uri).read_text(f"suites/{args.suite}/suite.json")
        if text is None:
            print(f"no suite {args.suite}")
            return 1
        ids += json.loads(text).get("run_ids", [])
    if args.all:
        ids += index.run_ids()
    judgements = []
    for rid in dict.fromkeys(ids):
        try:
            jd = Run.load(_run_store(cfg, index, rid), rid).judgement
        except ArchiveError:
            continue
        if jd:
            judgements.append(jd)
    res = panel.corpus_alpha(judgements)
    print(
        f"{len(judgements)} judged runs, {res['units']} units, {res['coders']} judges: "
        f"Krippendorff's alpha (ordinal) = {res['alpha']}, 95% CI {res['ci95']}"
    )
    return 0


def cmd_lgnd_login(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from tools.lgnd import login as lgnd

    secret = args.secret or cfg.get("lgnd_secret_id")
    if not secret:
        print("lgnd_secret_id is not set in harness.yaml; deploy with CDK first (output LgndSecretArn).")
        return 2
    if args.device:
        return lgnd.login_device(secret, cfg["region"])
    return lgnd.login_browser(secret, cfg["region"])


def cmd_ui(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness.web import app

    return app.serve(cfg, args.port)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="Track 1 evaluation harness")
    p.add_argument("--config", default=None, help="path to harness.yaml (default: ./harness.yaml)")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the agent on a prompt and report it")
    what = run.add_mutually_exclusive_group(required=True)
    what.add_argument("--prompt", help="prompt file, e.g. prompts/tasks/dallas-dc.md")
    what.add_argument("--suite", help="suite file, e.g. suites/dallas-dc-v1.yaml")
    run.add_argument("--model", default=None, help="model key from harness.yaml models")
    run.add_argument("--backend", choices=["agentcore", "local"], default=None)
    ui = sub.add_parser("ui", help="the Team Foundry console: run, watch, score, map")
    ui.add_argument("--port", type=int, default=8787)
    lg = sub.add_parser(
        "lgnd-login", help="one-time OAuth browser login to LGND Geo; saves to Secrets Manager"
    )
    lg.add_argument("--secret", default=None, help="secret ID (default: lgnd_secret_id in harness.yaml)")
    lg.add_argument("--device", action="store_true", help="use the device-code flow instead of the browser")
    j = sub.add_parser("judge", help="score an archived run with the judge panel (docs/judging)")
    j.add_argument("run_id")
    j.add_argument("--passes", type=int, default=None, help="judge N times for repeat stability")
    cal = sub.add_parser(
        "calibrate", help="plant known defects in a run's dossier and check the panel sees them"
    )
    cal.add_argument("run_id")
    cal.add_argument("--passes", type=int, default=1)
    ag = sub.add_parser("agreement", help="Krippendorff's alpha of the judges across a set of judged runs")
    ag.add_argument("run_ids", nargs="*")
    ag.add_argument("--suite", default=None)
    ag.add_argument("--all", action="store_true", help="every run in out/index.json")
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
            "ui": cmd_ui,
            "judge": cmd_judge,
            "calibrate": cmd_calibrate,
            "agreement": cmd_agreement,
        }[args.command]
        return handler(cfg, index, args)
    except (ArchiveError, FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
