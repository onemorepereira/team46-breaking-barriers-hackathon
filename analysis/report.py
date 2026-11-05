"""AC8 per-run report and AC11 comparison, rendered as static HTML with autoescape (design: Security)."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markdown_it import MarkdownIt

from analysis import check, licences, provenance, signals, summary
from analysis import reference as ref_mod
from analysis.judging import measure, panel, rubric
from analysis.judging.explain import explain
from analysis.trace import Run

_env = Environment(loader=PackageLoader("analysis", "templates"), autoescape=select_autoescape(default=True))
# The agent's answer is Markdown. CommonMark plus tables, with raw HTML off: any HTML in the text is escaped,
# and markdown-it refuses javascript: and data: links, so the rendered answer can't inject markup.
_md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def markdown(text: str | None) -> str:
    """HTML for the template's `| markdown | safe`: safe because markdown-it escapes all input HTML."""
    return _md.render(text or "")


def claims_blocks(final_output: str) -> list[str]:
    """The fenced JSON blocks of the answer, pretty-printed (left raw if they don't parse)."""
    out = []
    for block in provenance.FENCE_RE.findall(final_output or ""):
        try:
            out.append(json.dumps(json.loads(block), indent=1, ensure_ascii=False))
        except ValueError:
            out.append(block)
    return out


_env.filters["markdown"] = markdown


@dataclass
class RunReport:
    run: Run
    missing: list[check.Missing]
    prov: provenance.Provenance
    sig: signals.Signals
    summ: summary.Summary
    tools: list[dict[str, Any]]
    datasets: list[dict[str, str]]
    measured: measure.Measured
    panel: panel.PanelResult | None
    judgement: dict[str, Any] | None
    plain_names: dict[str, str]
    reference: dict[str, Any] | None = None
    licences: dict[str, Any] | None = None


def reference_of(run: Run, m: measure.Measured, prov: provenance.Provenance,
                 repo_sha: str | None = None) -> dict[str, Any] | None:  # fmt: skip
    claims = [(x.lat, x.lon) for x in m.located if x.source == "claim"]
    # every LGND search result per call, not deduplicated across calls (docs/ranking-metrics); untied runs
    # have no reference to rank against, so skip the parse
    tied = run.store.read_text(f"runs/{run.run_id}/{ref_mod.SNAPSHOT}/tie.json")
    chips = measure.search_candidates(run) if tied else None
    return ref_mod.from_run(run, claims, prov.claims_block_missing, repo_sha, chips)


def licences_of(
    run: Run, reference: dict[str, Any] | None, narrative_model: str | None = None
) -> dict[str, Any]:
    judges = [str(s.get("key")) for s in (run.judgement or {}).get("seats", []) if s.get("key")]
    ref = reference if reference and not reference.get("error") else None
    return licences.for_run(run, ref, judges, narrative_model)


def analyze(
    run: Run,
    rubric_path: str | None = None,
    repo_sha: str | None = None,
    narrative_model: str | None = None,
) -> RunReport:
    prov = provenance.grade(run)
    measured = measure.measure(run, prov)
    ref = reference_of(run, measured, prov, repo_sha)
    return RunReport(
        run=run,
        missing=check.check_run(run),
        prov=prov,
        sig=signals.compute(run),
        summ=summary.build(run, prov),
        tools=signals.tools_available(run),
        datasets=signals.datasets_accessed(run),
        measured=measured,
        panel=panel.rescore(run.judgement, run, measured) if run.judgement else None,
        judgement=run.judgement,
        plain_names=(
            rubric.display_names(rubric.parse(run.judgement["rubric"]["snapshot"]), rubric_path)
            if run.judgement
            else {}
        ),
        reference=ref,
        licences=licences_of(run, ref, narrative_model),
    )


def render_run(rep: RunReport, generated_at: str) -> str:
    return _env.get_template("report.html").render(
        r=rep,
        m=rep.run.manifest,
        generated_at=generated_at,
        answer=measure.answer_text(rep.run.final_output),
        claims_json=claims_blocks(rep.run.final_output),
        explanation=explain(rep.run, rep.panel, measured=rep.measured),
        conditions=rep.measured.conditions,
        source_check_note=provenance.matcher_update_note(rep.judgement),
    )


COMPARE_COLUMNS = [
    "run_id", "prompt_file", "model_key", "model_id", "status", "steps", "tool_calls", "errors", "retries",
    "input_tokens", "output_tokens", "estimated_cost_usd", "runtime_s", "matched", "mismatch", "unsourced",
    "claims_block_missing", "claims_in_area", "search_footprint", "score", "workflow_score", "output_score",
    "confidence", "within_one", "judging_cost_usd", "datasets_accessed",
    "concept", "place", "role", "site_recall", "cell_precision", "count_ratio",
    "recall_at_k", "auroc", "ap", "effort_80",
]  # fmt: skip


def compare_rows(reports: list[RunReport]) -> list[dict[str, Any]]:
    rows = []
    for rep in reports:
        m, c = rep.run.manifest, rep.prov.counts()
        rows.append(
            {
                "run_id": rep.run.run_id,
                "prompt_file": m.get("prompt_file"),
                "model_key": m.get("model_key"),
                "model_id": m.get("model_id"),
                "status": rep.run.status,
                **{k: getattr(rep.sig, k) for k in ("steps", "tool_calls", "errors", "retries")},
                **{k: getattr(rep.sig, k) for k in ("input_tokens", "output_tokens", "estimated_cost_usd")},
                "runtime_s": rep.sig.runtime_s,
                **c,
                "claims_block_missing": rep.prov.claims_block_missing,
                "claims_in_area": f"{rep.measured.claims_inside}/{rep.measured.claims_located}",
                "search_footprint": f"{rep.measured.chips_inside}/{rep.measured.chips_total}",
                "score": rep.panel.overall if rep.panel else None,
                "workflow_score": rep.panel.dimensions.get("workflow") if rep.panel else None,
                "output_score": rep.panel.dimensions.get("output") if rep.panel else None,
                "confidence": rep.panel.confidence if rep.panel else None,
                "within_one": rep.panel.within_one if rep.panel else None,
                "judging_cost_usd": (rep.judgement or {}).get("judging_cost_usd"),
                "datasets_accessed": "; ".join(d["dataset"] for d in rep.datasets),
                **_meta_cols(rep),
            }
        )
    return rows


def _meta_cols(rep: RunReport) -> dict[str, Any]:
    meta = rep.run.manifest.get("suite_meta") or {}
    ref = rep.reference if rep.reference and not rep.reference.get("error") else {}
    return {
        "concept": meta.get("concept"),
        "place": meta.get("place"),
        "role": meta.get("role"),
        "site_recall": ref.get("site_recall"),
        "cell_precision": ref.get("cell_precision"),
        "count_ratio": ref.get("count_ratio"),
        **_ranking_cols(ref.get("ranking") or {}),
    }


def _ranking_cols(rk: dict[str, Any]) -> dict[str, Any]:
    """The ranking metrics in compare (docs/ranking-metrics AC6); effort_80 is None when not reached."""
    effort = (rk.get("effort") or {}).get("80") or {}
    return {"recall_at_k": rk.get("recall_at_k"), "auroc": rk.get("auroc"), "ap": rk.get("ap"),
            "effort_80": effort.get("cells")}  # fmt: skip


def _mean(vals: list[Any]) -> float | None:
    xs = [float(v) for v in vals if v is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


CONCEPT_COLUMNS = [
    "kind",
    "concept",
    "model_key",
    "runs",
    "score",
    "site_recall",
    "cell_precision",
    "count_ratio",
    "recall_at_k",
    "auroc",
    "ap",
    "effort_80",
    "n_home",
    "n_transfer",
    "score_home",
    "score_transfer",
    "score_gap",
    "recall_home",
    "recall_transfer",
    "recall_gap",
]


def concept_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per asset class (the benchmark reports per class, not one aggregate): docs/adb-alignment AC9."""
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("concept"):
            by.setdefault(str(r["concept"]), []).append(r)
    return [
        {
            "kind": "concept",
            "concept": c,
            "runs": len(rs),
            "score": _mean([r["score"] for r in rs]),
            "site_recall": _mean([r["site_recall"] for r in rs]),
            "cell_precision": _mean([r["cell_precision"] for r in rs]),
            "count_ratio": _mean([r["count_ratio"] for r in rs]),
            "recall_at_k": _mean([r.get("recall_at_k") for r in rs]),
            "auroc": _mean([r.get("auroc") for r in rs]),
            "ap": _mean([r.get("ap") for r in rs]),
            "effort_80": _mean([r.get("effort_80") for r in rs]),
        }
        for c, rs in sorted(by.items())
    ]


def transfer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per (concept, model): home minus transfer, each side the mean over its runs that have a value."""
    by: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        if r.get("concept") and r.get("role") in ("home", "transfer"):
            by.setdefault((str(r["concept"]), str(r["model_key"])), {}).setdefault(str(r["role"]), []).append(
                r
            )
    out = []
    for (c, mk), sides in sorted(by.items()):
        if not sides.get("home") or not sides.get("transfer"):
            continue
        h, t = sides["home"], sides["transfer"]
        sh, st = _mean([r["score"] for r in h]), _mean([r["score"] for r in t])
        rh, rt = _mean([r["site_recall"] for r in h]), _mean([r["site_recall"] for r in t])
        out.append(
            {
                "kind": "transfer",
                "concept": c,
                "model_key": mk,
                "n_home": sum(1 for r in h if r["score"] is not None),
                "n_transfer": sum(1 for r in t if r["score"] is not None),
                "score_home": sh,
                "score_transfer": st,
                "score_gap": None if sh is None or st is None else round(sh - st, 3),
                "recall_home": rh,
                "recall_transfer": rt,
                "recall_gap": None if rh is None or rt is None else round(rh - rt, 3),
            }
        )
    return out


def concepts_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CONCEPT_COLUMNS)
    w.writeheader()
    w.writerows([*concept_rows(rows), *transfer_rows(rows)])
    return buf.getvalue()


def render_compare(
    suite_id: str, rows: list[dict[str, Any]], generated_at: str, agreement: dict[str, Any] | None = None
) -> str:
    return _env.get_template("compare.html").render(
        suite_id=suite_id, rows=rows, columns=COMPARE_COLUMNS, generated_at=generated_at, agreement=agreement,
        concepts=concept_rows(rows), transfers=transfer_rows(rows),
    )  # fmt: skip


def compare_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COMPARE_COLUMNS)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
