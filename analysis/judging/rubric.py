"""Rubric files (rubrics/*.yaml): load and validate (spec AC1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DIMENSIONS = ("workflow", "output")
KINDS = ("judged", "measured")
MEASURED = ("claim_provenance", "area_compliance")  # the measured criteria code knows how to compute


class RubricError(ValueError):
    pass


@dataclass(frozen=True)
class Criterion:
    id: str
    dimension: str
    kind: str
    question: str
    anchors: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Rubric:
    id: str
    version: int
    title: str
    scale: tuple[int, ...]
    criteria: tuple[Criterion, ...]
    failure_modes: dict[str, str]
    fatal: dict[str, str]
    calibration: dict[str, str]  # perturbation -> judged criterion it must lower
    raw: dict[str, Any]
    sha256: str

    @property
    def judged(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "judged"]

    @property
    def measured(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "measured"]

    @property
    def max_score(self) -> int:
        return max(self.scale)


def _need(d: Any, key: str, where: str, typ: type | tuple[type, ...]) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise RubricError(f"{where}: missing {key}")
    if not isinstance(d[key], typ):
        raise RubricError(f"{where}.{key}: expected {getattr(typ, '__name__', typ)}")
    return d[key]


def parse(raw: Any) -> Rubric:
    if not isinstance(raw, dict):
        raise RubricError("rubric: expected a mapping")
    scale = tuple(_need(raw, "scale", "rubric", list))
    if not scale or not all(isinstance(s, int) for s in scale):
        raise RubricError("rubric.scale: expected a list of integers")
    criteria, seen = [], set()
    for i, c in enumerate(_need(raw, "criteria", "rubric", list)):
        where = f"criteria[{i}]"
        cid = _need(c, "id", where, str)
        if cid in seen:
            raise RubricError(f"{where}.id: duplicate {cid}")
        seen.add(cid)
        dim, kind = _need(c, "dimension", where, str), _need(c, "kind", where, str)
        if dim not in DIMENSIONS:
            raise RubricError(f"{where}.dimension: {dim!r} is not one of {', '.join(DIMENSIONS)}")
        if kind not in KINDS:
            raise RubricError(f"{where}.kind: {kind!r} is not one of {', '.join(KINDS)}")
        anchors: dict[int, str] = {}
        if kind == "judged":
            a = _need(c, "anchors", where, dict)
            for s in scale:
                text = a.get(s, a.get(str(s)))  # JSON snapshots turn integer keys into strings
                if text is None or not str(text).strip():
                    raise RubricError(f"{where}.anchors: missing {s}")
                anchors[s] = str(text).strip()
        elif cid not in MEASURED:
            raise RubricError(f"{where}.id: no code measures {cid!r} (known: {', '.join(MEASURED)})")
        criteria.append(Criterion(cid, dim, kind, _need(c, "question", where, str).strip(), anchors))
    if not any(c.kind == "judged" for c in criteria):
        raise RubricError("rubric.criteria: needs at least one judged criterion")

    def ids(key: str) -> dict[str, str]:
        out = {}
        for i, f in enumerate(raw.get(key) or []):
            out[_need(f, "id", f"{key}[{i}]", str)] = str(f.get("meaning", "")).strip()
        return out

    calibration = raw.get("calibration") or {}
    if not isinstance(calibration, dict):
        raise RubricError("rubric.calibration: expected a mapping of perturbation -> criterion id")
    judged_ids = {c.id for c in criteria if c.kind == "judged"}
    for k, v in calibration.items():
        if v not in judged_ids:
            raise RubricError(f"rubric.calibration.{k}: {v!r} is not a judged criterion")
    text = json.dumps(json.loads(json.dumps(raw)), sort_keys=True)  # same hash after a JSON round trip
    return Rubric(
        id=str(_need(raw, "id", "rubric", str)),
        version=int(_need(raw, "version", "rubric", int)),
        title=str(raw.get("title", "")),
        scale=scale,
        criteria=tuple(criteria),
        failure_modes=ids("failure_modes"),
        fatal=ids("fatal"),
        calibration={str(k): str(v) for k, v in calibration.items()},
        raw=raw,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def load(path: str | Path) -> Rubric:
    p = Path(path)
    if not p.is_file():
        raise RubricError(f"rubric file {p} not found")
    return parse(yaml.safe_load(p.read_text(encoding="utf-8")))
