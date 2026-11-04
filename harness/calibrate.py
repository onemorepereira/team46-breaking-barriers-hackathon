"""`harness calibrate` (spec AC9): plant one defect at a time in a run's dossier and check the panel notices.

Each perturbation must lower the panel median of the criterion the rubric's `calibration` map names for it. A
judge panel that can't see a planted defect can't be trusted to see a real one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from analysis.judging import dossier as dossier_mod
from analysis.judging.rubric import Rubric
from analysis.judging.rubric import load as load_rubric
from analysis.trace import Run
from core.store import Store
from harness import judge
from harness.config import Config


def _medians(r: Rubric, passes: list[dict[str, Any]]) -> dict[str, float | None]:
    """Mean over passes of each judged criterion's lower median (gates are not applied in calibration)."""
    out: dict[str, float | None] = {}
    for c in r.judged:
        meds = []
        for p in passes:
            votes = sorted(int(j["scores"][c.id]) for j in p["judges"] if j.get("status") == "ok")
            if len(votes) >= 3:
                meds.append(float(votes[(len(votes) - 1) // 2]))
        out[c.id] = sum(meds) / len(meds) if meds else None
    return out


def verdicts(r: Rubric, base: dict[str, float | None], perturbed: dict[str, dict[str, float | None]]
             ) -> list[dict[str, Any]]:  # fmt: skip
    rows: list[dict[str, Any]] = []
    for kind in dossier_mod.PERTURBATIONS:
        target = r.calibration.get(kind)
        if target is None:
            rows.append({"perturbation": kind, "target": None, "verdict": "skipped"})
            continue
        after = perturbed.get(kind, {})
        b, a = base.get(target), after.get(target)
        others = [
            (base[c] or 0) - (after.get(c) or 0)
            for c in base if c != target and base.get(c) is not None and after.get(c) is not None
        ]  # fmt: skip
        other_drop = max(others) if others else 0.0
        if b is None or a is None:
            verdict, drop = "inconclusive", None
        elif b == 0:
            verdict, drop = "inconclusive", 0.0
        else:
            drop = b - a
            verdict = "pass" if drop > 0 else "fail"
        rows.append({"perturbation": kind, "target": target, "original": b, "perturbed": a, "drop": drop,
                     "max_other_drop": other_drop,
                     "non_specific": drop is not None and drop > 0 and other_drop >= drop,
                     "verdict": verdict})  # fmt: skip
    return rows


def exit_code(rows: list[dict[str, Any]]) -> int:
    if any(r["verdict"] == "fail" for r in rows):
        return 1
    return 0 if any(r["verdict"] == "pass" for r in rows) else 2


def calibrate(cfg: Config, run: Run, store: Store, passes: int = 1, client: Any = None) -> dict[str, Any]:
    j = judge.judging_cfg(cfg)
    r = load_rubric(j["rubric"])
    seats = judge.seats(cfg, run.manifest.get("model_key"), run.manifest.get("model_id"))
    d = dossier_mod.build(run)
    base_passes = judge.run_panel(cfg, r, d, seats, passes, client)
    base = _medians(r, base_passes)
    perturbed, cost = {}, sum(x.get("cost_usd") or 0 for p in base_passes for x in p["judges"])
    for kind in dossier_mod.PERTURBATIONS:
        if kind not in r.calibration:
            continue
        ps = judge.run_panel(cfg, r, dossier_mod.perturb(d, kind), seats, passes, client)
        perturbed[kind] = _medians(r, ps)
        cost += sum(x.get("cost_usd") or 0 for p in ps for x in p["judges"])
    rows = verdicts(r, base, perturbed)
    out = {"schema_version": 1, "run_id": run.run_id, "rubric": {"id": r.id, "sha256": r.sha256},
           "calibrated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "passes": passes,
           "seats": [s.key for s in seats], "original": base, "perturbed": perturbed, "rows": rows,
           "cost_usd": round(cost, 4), "exit_code": exit_code(rows)}  # fmt: skip
    store.write_text(f"runs/{run.run_id}/calibration.json", json.dumps(out, indent=1))
    return out
