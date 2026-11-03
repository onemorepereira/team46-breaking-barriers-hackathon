"""Local index of where each run and suite was archived (out/index.json; design: Finding a run's archive)."""

from __future__ import annotations

import json
from pathlib import Path


class Index:
    def __init__(self, out_dir: str | Path) -> None:
        self.path = Path(out_dir) / "index.json"

    def _load(self) -> dict[str, dict[str, str]]:
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {"runs": data.get("runs", {}), "suites": data.get("suites", {})}
        return {"runs": {}, "suites": {}}

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")

    def record_run(self, run_id: str, archive_uri: str) -> None:
        data = self._load()
        data["runs"][run_id] = archive_uri
        self._save(data)

    def record_suite(self, suite_id: str, archive_uri: str) -> None:
        data = self._load()
        data["suites"][suite_id] = archive_uri
        self._save(data)

    def run_uri(self, run_id: str) -> str | None:
        return self._load()["runs"].get(run_id)

    def suite_uri(self, suite_id: str) -> str | None:
        return self._load()["suites"].get(suite_id)
