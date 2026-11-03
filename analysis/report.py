"""AC8 per-run report and AC11 comparison, rendered as static HTML with autoescape (design: Security)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from analysis import check, provenance, score, signals, summary
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
    scores: list[score.CriterionScore] | None


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
        scores=score.score(run),
    )


def render_run(rep: RunReport, generated_at: str) -> str:
    return _env.get_template("report.html").render(r=rep, m=rep.run.manifest, generated_at=generated_at)


COMPARE_COLUMNS = [
    "run_id", "prompt_file", "model_key", "model_id", "status", "steps", "tool_calls", "errors", "retries",
    "input_tokens", "output_tokens", "estimated_cost_usd", "runtime_s", "matched", "mismatch", "unsourced",
    "claims_block_missing", "datasets_accessed",
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
                "datasets_accessed": "; ".join(d["dataset"] for d in rep.datasets),
            }
        )
    return rows


def render_compare(suite_id: str, rows: list[dict[str, Any]], generated_at: str) -> str:
    return _env.get_template("compare.html").render(
        suite_id=suite_id, rows=rows, columns=COMPARE_COLUMNS, generated_at=generated_at
    )


def compare_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COMPARE_COLUMNS)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
