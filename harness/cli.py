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


def write_report(cfg: config_mod.Config, run: Run, archive_tiles: bool = True) -> Path:
    out = Path(cfg["out_dir"]) / run.run_id
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.html"
    path.write_text(report.render_run(report.analyze(run), _now()), encoding="utf-8")
    from harness import rows

    rows.save(cfg["out_dir"], run)  # the runs table row, kept in step with the report
    if archive_tiles:
        archive_tiles_quietly(cfg, run)
    return path


def archive_tiles_quietly(cfg: config_mod.Config, run: Run) -> dict[str, int] | None:
    """Copy the run's result tiles into its archive (docs/tile-cache AC1). Never fails the caller."""
    from harness import tiles

    if not tiles.settings(cfg)["archive"]:
        return None
    try:
        counts = tiles.archive_run_tiles(cfg, run)
    except Exception as e:  # noqa: BLE001 - tiles are a convenience; the report stands without them
        print(f"run {run.run_id}: tile archiving failed ({e})", file=sys.stderr)
        return None
    if counts["failed"]:
        print(f"run {run.run_id}: tiles {counts}", file=sys.stderr)
    return counts


def cmd_replay(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    run = Run.load(_run_store(cfg, index, args.run_id), args.run_id)
    path = write_report(cfg, run)
    print(f"replayed {args.run_id} → {path}")
    jd = run.judgement
    if jd and jd.get("revision"):  # a human-prompted revision: show both scores, from the archive alone
        from harness import feedback, judge

        prev = feedback.previous_judgement(run.store, run.run_id, str(jd["revision"].get("previous")))
        before = judge.rescore(prev, run).overall if prev else None
        after = judge.rescore(jd, run).overall
        rv = jd["revision"]
        print(f"  revised after {rv.get('reviewer')}'s review {rv.get('review_id')}: {before} → {after}")
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
    reports, runs = [], []
    for run_id in suite["run_ids"]:
        try:
            run = Run.load(open_store(index.run_uri(run_id) or uri), run_id)
            reports.append(report.analyze(run))
            runs.append(run)
        except ArchiveError as e:
            print(f"warning: {e}", file=sys.stderr)
    rows = report.compare_rows(reports)
    out = Path(cfg["out_dir"]) / args.suite_id
    out.mkdir(parents=True, exist_ok=True)
    from analysis.judging import panel

    judged = [jd for run in runs if (jd := run.unrevised_judgement)]  # no human-influenced votes
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
    if jd.get("not_scored"):
        return 1
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
        sub = f" (standing in for {ev['stood_in_for']})" if ev.get("stood_in_for") else ""
        print(f"  pass {ev.get('pass')} {ev.get('key')}{sub}: {tail} ({ev.get('latency_s')} s)")
    elif ev.get("type") == "not_scored":
        print(f"not scored: no model call succeeded, so there is nothing to judge ({ev.get('cause')})")


def cmd_calibrate(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import calibrate

    store = _run_store(cfg, index, args.run_id)
    if args.feedback:
        fo = calibrate.feedback_check(cfg, Run.load(store, args.run_id), store)
        print(f"feedback check of {args.run_id} (panel: {', '.join(fo['seats'])}):")
        for row in fo["rows"]:
            print(f"  {row['check']:<13} {row['verdict']:<12} {row.get('why', '')}")
        print(f"cost ${fo['cost_usd']:.3f} → runs/{args.run_id}/calibration-feedback.json")
        return int(fo["exit_code"])
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
    if args.human:
        from analysis.judging import feedback as fb
        from harness import feedback

        dstore = feedback.deployment_store(cfg)
        reviews = feedback.rubric_reviews(dstore, feedback.active_rubric(cfg))
        if ids:
            reviews = [rv for rv in reviews if rv["run_id"] in set(ids)]
        groups = fb.human_agreement(fb.human_scores(reviews))["by_guidance"]
        if not groups:
            print("no reviews yet: review runs in the console (Your review) or with `harness review`")
            return 1
        for key, g in groups.items():
            print(
                f"panel vs reviewers (guidance {key}): {g['runs']} runs, {g['n']} units, alpha {g['alpha']}, "
                f"95% CI {g['ci95']}, mean abs diff {g['mad']}, exact {g['exact']}"
            )
        return 0
    judgements = []
    for rid in dict.fromkeys(ids):
        try:
            jd = Run.load(_run_store(cfg, index, rid), rid).unrevised_judgement
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


def cmd_review(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    """`harness review <run> --reviewer NAME --criterion id=agree | id=score:reason[@T3,M2]` (scripting)."""
    from harness import feedback

    criteria: dict[str, dict[str, object]] = {}
    for spec in args.criterion:
        cid, _, rest = spec.partition("=")
        if rest == "agree":
            criteria[cid] = {"agree": True}
            continue
        score, _, reason = rest.partition(":")
        reason, _, refs = reason.partition("@")
        criteria[cid] = {"score": score, "reason": reason, "refs": [x for x in refs.split(",") if x]}
    store = _run_store(cfg, index, args.run_id)
    body = {"reviewer": args.reviewer, "criteria": criteria, "note": args.note or ""}
    rv = feedback.create_review(cfg, feedback.deployment_store(cfg), Run.load(store, args.run_id), body)
    print(
        f"review {rv['id']} of {args.run_id} stored; `harness reconsider {args.run_id} {rv['id']}` to apply"
    )
    return 0


def cmd_reconsider(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import feedback

    store = _run_store(cfg, index, args.run_id)
    run = Run.load(store, args.run_id)
    before = (run.judgement or {}).get("panel", {}).get("overall")
    jd = feedback.reconsider(
        cfg, run, store, feedback.deployment_store(cfg), args.review_id, on_event=_print_judge
    )
    write_report(cfg, Run.load(store, args.run_id))
    print(f"{args.run_id}: {before} → {jd['panel']['overall']} after review {args.review_id}")
    return 0


def cmd_guidance(cfg: config_mod.Config, index: Index, args: argparse.Namespace) -> int:
    from harness import feedback

    store = feedback.deployment_store(cfg)
    if args.action == "list":
        o = feedback.overview(cfg, store)
        r = o["rubric"]
        print(
            f"guidance for {r['id']} v{r['version']} in {cfg['archive_uri']}: "
            f"active {o['active'].get('version')}"
        )
        print(f"  {o['reviews']} reviews of {o['reviewed_runs']} runs ({o['held_out_runs']} held out)")
        for v in o["versions"]:
            ev = (v.get("latest_evaluation") or {}).get("verdict")
            print(
                f"  v{v['version']:<3} {v['status']:<8} {v['lessons']} lessons, "
                f"by {v['created_by']}, eval {ev}"
            )
        return 0
    if args.action == "propose":
        v = feedback.propose(cfg, store, args.by)
        print(f"draft v{v['version']}: {len(v['lessons'])} lessons ({v['proposal']['dropped']} dropped)")
        for x in v["lessons"]:
            print(f"  {x['id']} {x['criterion']}: {x['text']}")
        return 0
    if args.action == "evaluate":
        est = feedback.estimate(cfg, store, index, args.version)
        print(f"{est['held_out']} held-out runs, {est['passes']} panel passes, about ${est['estimate_usd']}")
        if est["passes"] and not args.yes and input("Run it? [y/N] ").strip().lower() != "y":
            return 1

        def progress(ev: dict[str, object]) -> None:
            if ev.get("type") == "evaluating":
                print(
                    f"  {ev.get('done', '')}/{ev.get('total', '')} "
                    f"{ev.get('run_id', '')} {ev.get('stage', '')}"
                )

        rep = feedback.evaluate(cfg, store, index, args.version, on_event=progress)
        print(f"v{args.version}: {rep['verdict']}" + "".join(f"\n  - {x}" for x in rep.get("reasons") or []))
        return 0 if rep["verdict"] == "adopt" else 1
    if args.action == "approve":
        v = feedback.approve(cfg, store, args.version, args.by, args.reason or "")
        print(f"v{v['version']} is now active for this deployment")
        return 0
    feedback.switch_off(cfg, store, args.by, args.reason or "")
    print("guidance switched off for this deployment")
    return 0


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
    cal.add_argument("--feedback", action="store_true", help="check the judges resist wrong reviews instead")
    ag = sub.add_parser("agreement", help="Krippendorff's alpha of the judges across a set of judged runs")
    ag.add_argument("run_ids", nargs="*")
    ag.add_argument("--suite", default=None)
    ag.add_argument("--all", action="store_true", help="every run in out/index.json")
    ag.add_argument("--human", action="store_true", help="the panel against reviewers (docs/judge-feedback)")
    rv = sub.add_parser("review", help="review a run's judgement (as the console's Your review card does)")
    rv.add_argument("run_id")
    rv.add_argument("--reviewer", required=True)
    rv.add_argument("--criterion", action="append", default=[], help="id=agree or id=score:reason[@T3,M2]")
    rv.add_argument("--note", default="")
    rc = sub.add_parser("reconsider", help="the judges reconsider a run with a review")
    rc.add_argument("run_id")
    rc.add_argument("review_id")
    g = sub.add_parser(
        "guidance", help="this deployment's judging guidance: list, propose, evaluate, approve, off"
    )
    gs = g.add_subparsers(dest="action", required=True)
    gs.add_parser("list")
    gp = gs.add_parser("propose")
    gp.add_argument("--by", required=True)
    ge = gs.add_parser("evaluate")
    ge.add_argument("version", type=int)
    ge.add_argument("--yes", action="store_true", help="don't ask before spending")
    ga = gs.add_parser("approve")
    ga.add_argument("version", type=int)
    ga.add_argument("--by", required=True)
    ga.add_argument("--reason", default="")
    go = gs.add_parser("off")
    go.add_argument("--by", required=True)
    go.add_argument("--reason", default="")
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
            "review": cmd_review,
            "reconsider": cmd_reconsider,
            "guidance": cmd_guidance,
        }[args.command]
        return handler(cfg, index, args)
    except (ArchiveError, FileNotFoundError, ValueError) as e:  # FeedbackError is a ValueError
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        from harness.judge import JudgeError

        if not isinstance(e, JudgeError):
            raise
        print(f"judging failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
