"""Krippendorff's alpha (nominal, ordinal, interval) from the coincidence matrix.

Checked against Krippendorff's published example ("Computing Krippendorff's Alpha-Reliability", 2011): nominal
0.743, ordinal 0.815, interval 0.849 (tests/test_judging.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import permutations


def alpha(data: Sequence[Sequence[float | None]], level: str = "ordinal") -> float | None:
    """data[coder][unit]; None is a missing value. Returns None when there's no variance to measure."""
    units = list(zip(*data, strict=True)) if data else []
    o: dict[tuple[float, float], float] = {}
    for unit in units:
        vals = [v for v in unit if v is not None]
        m = len(vals)
        if m < 2:
            continue
        for a, b in permutations(range(m), 2):
            o[(vals[a], vals[b])] = o.get((vals[a], vals[b]), 0.0) + 1 / (m - 1)
    values = sorted({v for pair in o for v in pair})
    n_c = {v: sum(w for (a, _), w in o.items() if a == v) for v in values}
    n = sum(n_c.values())
    if n <= 1 or len(values) < 2:
        return None

    def delta(c: float, k: float) -> float:
        if level == "nominal":
            return 0.0 if c == k else 1.0
        if level == "interval":
            return (c - k) ** 2
        if level == "ordinal":
            lo, hi = sorted((values.index(c), values.index(k)))
            between = sum(n_c[values[g]] for g in range(lo, hi + 1))
            return (between - (n_c[values[lo]] + n_c[values[hi]]) / 2) ** 2
        raise ValueError(f"unknown level {level!r}")

    d_o = sum(w * delta(c, k) for (c, k), w in o.items())
    d_e = sum(n_c[c] * n_c[k] * delta(c, k) for c in values for k in values) / (n - 1)
    if d_e == 0:
        return None
    return 1 - d_o / d_e
