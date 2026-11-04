"""AC8 per-run report and AC11 comparison, rendered as static HTML with autoescape (design: Security)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from analysis import check, provenance, signals, summary
from analysis.judging import measure, panel
from analysis.trace import Run

_env = Environment(loader=PackageLoader("analysis", "templates"), autoescape=select_autoescape(default=True))


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


def analyze(run: Run) -> RunReport:
    prov = provenance.grade(run)
    return RunReport(
        run=run,
        missing=check.check_run(run),
        prov=prov,
        sig=signals.compute(run),
        summ=summary.build(run, prov),
        tools=signals.tools_available(run),
        datasets=signals.datasets_accessed(run),
        measured=measure.measure(run, prov),
        panel=panel.rescore(run.judgement, run) if run.judgement else None,
        judgement=run.judgement,
    )


def render_run(rep: RunReport, generated_at: str) -> str:
    return _env.get_template("report.html").render(r=rep, m=rep.run.manifest, generated_at=generated_at)


COMPARE_COLUMNS = [
    "run_id", "prompt_file", "model_key", "model_id", "status", "steps", "tool_calls", "errors", "retries",
    "input_tokens", "output_tokens", "estimated_cost_usd", "runtime_s", "matched", "mismatch", "unsourced",
    "claims_block_missing", "claims_in_area", "search_footprint", "score", "workflow_score", "output_score",
    "confidence", "within_one", "judging_cost_usd", "datasets_accessed",
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
            }
        )
    return rows


def render_compare(
    suite_id: str, rows: list[dict[str, Any]], generated_at: str, agreement: dict[str, Any] | None = None
) -> str:
    return _env.get_template("compare.html").render(
        suite_id=suite_id, rows=rows, columns=COMPARE_COLUMNS, generated_at=generated_at, agreement=agreement
    )


def compare_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COMPARE_COLUMNS)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
