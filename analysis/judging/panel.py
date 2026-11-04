"""Panel aggregation (spec AC5-AC8): medians, gates, dimensions, failure modes, agreement, confidence."""

from __future__ import annotations

import random
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from analysis.judging import measure as measure_mod
from analysis.judging.alpha import alpha
from analysis.judging.measure import Measured
from analysis.judging.rubric import Rubric, parse

MIN_VALID = 3  # a full tribunal: fewer valid judges in a pass (after reserves stand in) and it is dropped


@dataclass
class CriterionResult:
    id: str
    dimension: str
    kind: str
    question: str
    score: float | None  # 0..100, None = N/A
    median: float | None = None  # judged: mean of pass medians on the 0..2 scale
    std: float | None = None  # judged: std of pass medians (passes > 1)
    votes: dict[str, int] = field(default_factory=dict)  # judge key -> pass-1 vote
    spread: float | None = None
    mad: float | None = None
    unanimous: bool | None = None
    value: str | None = None  # measured: "x/y"
    gated: bool = False


@dataclass
class PanelResult:
    status: str  # scored | insufficient
    overall: float | None
    dimensions: dict[str, float | None]
    criteria: list[CriterionResult]
    failure_modes: list[dict[str, Any]]
    gates: list[dict[str, str]]
    within_one: float | None
    mad: float | None
    valid_judges: list[int]  # per pass
    passes: int
    confidence: str
    confidence_reasons: list[str]
    verdict: str  # PASSED-ish label for the page: "scored" | "FAILED" | "not scored"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def lower_median(votes: list[int]) -> float:
    s = sorted(votes)
    return float(s[(len(s) - 1) // 2])


def _valid(pass_: dict[str, Any]) -> list[dict[str, Any]]:
    return [j for j in pass_.get("judges", []) if j.get("status") == "ok"]


def aggregate(rubric: Rubric, passes: list[dict[str, Any]], measured: Measured) -> PanelResult:
    usable = [p for p in passes if len(_valid(p)) >= MIN_VALID]
    valid_counts = [len(_valid(p)) for p in passes]
    gates = list(measured.gates)
    top = rubric.max_score
    results: list[CriterionResult] = []
    spreads, mads = [], []
    pass_within: dict[int, list[bool]] = {}  # pass index -> per criterion: all votes within one point?
    for c in rubric.criteria:
        if c.kind == "measured":
            share = measured.score_of(c.id)
            value = (
                f"{measured.claims_matched}/{measured.claims_total}"
                if c.id == "claim_provenance"
                else (
                    (
                        f"{measured.conditions_supported}/{measured.conditions_total}"
                        if measured.conditions_total
                        else "no location evidence"
                    )
                    if c.id == "condition_compliance"
                    else f"{measured.claims_inside}/{measured.claims_located}"
                )
            )
            results.append(
                CriterionResult(
                    c.id,
                    c.dimension,
                    c.kind,
                    c.question,
                    None if share is None else round(share * 100, 1),
                    value=value,
                )
            )
            continue
        medians, pass_spreads, pass_mads = [], [], []
        votes1: dict[str, int] = {}
        for i, p in enumerate(usable):
            v = {j["key"]: int(j["scores"][c.id]) for j in _valid(p) if c.id in j.get("scores", {})}
            if len(v) < MIN_VALID:
                continue
            med = lower_median(list(v.values()))
            medians.append(med)
            pass_spreads.append(max(v.values()) - min(v.values()))
            pass_within.setdefault(i, []).append(pass_spreads[-1] <= 1)
            pass_mads.append(sum(abs(x - med) for x in v.values()) / len(v))
            if i == 0:
                votes1 = v
        if not medians:
            results.append(CriterionResult(c.id, c.dimension, c.kind, c.question, None))
            continue
        mean_med = sum(medians) / len(medians)
        spread = sum(pass_spreads) / len(pass_spreads)
        mad = sum(pass_mads) / len(pass_mads)
        spreads.append(spread)
        mads.append(mad)
        results.append(
            CriterionResult(
                c.id,
                c.dimension,
                c.kind,
                c.question,
                round(mean_med / top * 100, 1),
                median=round(mean_med, 3),
                std=round(statistics.pstdev(medians), 3) if len(medians) > 1 else None,
                votes=votes1,
                spread=spread,
                mad=round(mad, 3),
                unanimous=spread == 0,
            )
        )
    if gates:
        for r in results:
            if r.dimension == "output":
                r.score, r.gated = 0.0, True
    dims: dict[str, float | None] = {}
    for d in ("workflow", "output"):
        vals = [r.score for r in results if r.dimension == d and r.score is not None]
        dims[d] = round(sum(vals) / len(vals), 1) if vals else None
    if not usable:
        dims = {d: None for d in dims}  # a dimension isn't scored on measured criteria alone
    # A good process cannot average away a missing required spatial constraint.
    output = dims.get("output")
    if measured.condition_compliance is not None and output is not None:
        dims["output"] = min(output, round(measured.condition_compliance * 100, 1))
    present = [v for v in dims.values() if v is not None]
    overall = round(sum(present) / len(present), 1) if present else None
    status = "scored" if usable else "insufficient"
    if gates:
        overall = 0.0
    elif not usable:
        overall = None
    # failure modes: majority of all votes pooled across usable passes
    tags: Counter[str] = Counter()
    voters = 0
    for p in usable:
        for j in _valid(p):
            voters += 1
            tags.update(set(j.get("failure_modes", [])))
    need = voters // 2 + 1
    modes = [
        {"id": t, "votes": n, "of": voters, "meaning": rubric.failure_modes.get(t, "")}
        for t, n in tags.most_common()
        if n >= need
    ]
    # within-one per pass (share of criteria whose votes span <= 1 point), averaged across passes (AC7)
    shares = [sum(w) / len(w) for w in pass_within.values() if w]
    within = sum(shares) / len(shares) if shares else None
    mad_all = round(sum(mads) / len(mads), 3) if mads else None
    seated = [sum(1 for j in p.get("judges", []) if not j.get("stood_in_for")) for p in passes]
    conf, reasons = confidence(measured, valid_counts, within, bool(usable), seated)
    if measured.conditions_need_review:
        if conf == "High":
            conf = "Medium"
        reasons.append("Some request conditions lack supporting evidence; review the conditions table")
    verdict = "FAILED" if gates else ("scored" if usable else "not scored")
    if measured.conditions_error and not gates:
        overall, status, verdict, conf = None, "insufficient", "not scored", "Low"
        reasons.append("Request condition extraction failed; evaluation is incomplete")
    return PanelResult(
        status,
        overall,
        dims,
        results,
        modes,
        gates,
        within,
        mad_all,
        valid_counts,
        len(passes),
        conf,
        reasons,
        verdict,
    )


def confidence(
    m: Measured, valid_counts: list[int], within: float | None, scored: bool, seated: list[int] | None = None
) -> tuple[str, list[str]]:
    """High / Medium / Low with reasons (spec AC7): agreement on the evidence, not ground truth.

    `seated` is each pass's number of seats. A pass short one vote (a judge failed and no reserve could
    stand in) is Medium; short two or more is Low."""
    low, med = [], []
    if not m.trace_integrity:
        low.append(
            f"trace integrity failed ({m.missing_fields} missing fields, {m.archive_errors} archive errors)"
        )
    if m.gates:
        low.append("fatal gate: " + ", ".join(g["id"] for g in m.gates))
    if not scored:
        low.append("not enough valid judges to score")
    if valid_counts and any(v < MIN_VALID for v in valid_counts):
        med.append(f"a judging pass was dropped (fewer than {MIN_VALID} valid judges)")
    for v, n in zip(valid_counts, seated or valid_counts, strict=False):
        if v >= MIN_VALID and n - v >= 2:
            low.append(f"only {v} of {n} judges valid in a pass")
            break
        if v >= MIN_VALID and n - v == 1:
            med.append(f"{v} of {n} judges valid")
            break
    if within is not None and within < 0.5:
        low.append(f"judges within one point on only {within:.0%} of criteria")
    elif within is not None and within < 0.8:
        med.append(f"judges within one point on {within:.0%} of criteria")
    if low:
        return "Low", low + med
    if med:
        return "Medium", med
    return "High", [
        f"trace intact, no gate, {min(valid_counts) if valid_counts else 0} valid judges in every pass, "
        f"judges within one point on {within:.0%} of criteria"
    ]


def corpus_alpha(judgements: list[dict[str, Any]], samples: int = 1000, seed: int = 7) -> dict[str, Any]:
    """Krippendorff's ordinal alpha over a set of judgements: coders = seat keys, units = run x criterion.

    Pass 1 only. The 95% CI is a cluster bootstrap over whole runs (a run's criteria are correlated).
    """
    runs: list[list[dict[str, int]]] = []
    for jd in judgements:
        passes = jd.get("passes") or []
        if not passes:
            continue
        valid = _valid(passes[0])
        if len(valid) < MIN_VALID:
            continue  # a dropped pass doesn't count toward agreement either
        run_units = []
        for cid in sorted({k for j in valid for k in j.get("scores", {})}):
            unit = {j["key"]: int(j["scores"][cid]) for j in valid if cid in j.get("scores", {})}
            if len(unit) >= 2:
                run_units.append(unit)
        if run_units:
            runs.append(run_units)
    units = [u for ru in runs for u in ru]
    coders = sorted({k for u in units for k in u})
    out: dict[str, Any] = {"alpha": None, "ci95": None, "units": len(units), "runs": len(runs),
                           "coders": len(coders)}  # fmt: skip
    if not units:
        return out

    def matrix(us: list[dict[str, int]]) -> list[list[float | None]]:
        return [[u.get(c) for u in us] for c in coders]

    a = alpha(matrix(units))
    out["alpha"] = None if a is None else round(a, 3)
    if len(runs) < 2:
        return out
    rng = random.Random(seed)
    boots = []
    for _ in range(samples):
        sample = [u for _ in runs for u in runs[rng.randrange(len(runs))]]
        b = alpha(matrix(sample))
        if b is not None:
            boots.append(b)
    boots.sort()
    if boots:
        out["ci95"] = [round(boots[int(0.025 * len(boots))], 3), round(boots[int(0.975 * len(boots)) - 1], 3)]
    return out


def rescore(judgement: dict[str, Any], run: Any) -> PanelResult:
    """Re-aggregate an archived judgement with current code against the rubric it was judged with (replay)."""
    r = parse(judgement["rubric"]["snapshot"])
    return aggregate(r, judgement.get("passes") or [], measure_mod.measure(run))
