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
    "rubric": None,
    "scorer": "none",
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


def load(path: str | Path | None = None) -> Config:
    p = Path(path) if path else Path("harness.yaml")
    data = dict(DEFAULTS)
    if p.is_file():
        loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{p}: expected a mapping at the top level")
        data.update(loaded)
        return Config(data, p)
    if path:
        raise FileNotFoundError(f"config file {p} not found")
    return Config(data, None)
