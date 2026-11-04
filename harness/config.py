"""harness.yaml loading (design: Data and contracts). No secrets live here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "region": "us-west-2",
    "archive_uri": "file://./archive",
    "local_archive_uri": "file://./archive",
    "backend": "agentcore",
    "local_exporter": "console",
    "runtime_arn": None,
    "models": {},
    "narrative_model": None,
    "max_runs_per_suite": 8,
    "max_suite_usd": 50,
    "prices_per_mtok": {},
    "judging": {},
    "area_mode": "enforce",  # enforce | observe | off: how the prompt's area is applied to LGND searches
    "out_dir": "out",
}


@dataclass
class Config:
    data: dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS))
    path: Path | None = None

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def local_path(p: Path) -> Path:
    """The personal override next to a config file: harness.yaml -> harness.local.yaml (git-ignored)."""
    return p.with_name(f"{p.stem}.local{p.suffix}")


def _read(p: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{p}: expected a mapping at the top level")
    return loaded


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Nested dicts merge key by key; anything else in `over` replaces the base value."""
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path: str | Path | None = None) -> Config:
    """harness.yaml (committed, shared), then harness.local.yaml beside it if present (git-ignored, yours).

    The local file holds what differs on your own AWS sandbox, e.g. archive_uri, lgnd_secret_id and
    runtime_arn from your stack's CDK outputs, so the committed harness.yaml never has to change.
    """
    p = Path(path) if path else Path("harness.yaml")
    data = dict(DEFAULTS)
    if p.is_file():
        data.update(_read(p))
        local = local_path(p)
        if local.is_file():
            data = _merge(data, _read(local))
        return Config(data, p)
    if path:
        raise FileNotFoundError(f"config file {p} not found")
    return Config(data, None)
