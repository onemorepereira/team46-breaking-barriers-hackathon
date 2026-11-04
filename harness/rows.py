"""One row of the console's runs table per finished run, saved next to its report as out/<id>/row.json.

Building a row reads the run's whole archive, 1-4 s for a run stored in S3. A row only changes when the run
is judged again, and every path that judges (or replays) a run rewrites its report through
`cli.write_report`, which saves the row too. So the runs list reads small local files and never re-reads the
archive of a run that hasn't changed. Bump ROW_VERSION when the row's shape changes, to rebuild old rows.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from analysis.trace import Run

ROW_VERSION = 1

_memo: dict[Path, tuple[int, dict[str, Any]]] = {}  # path -> (mtime_ns, row): skip re-parsing unchanged files
_memo_lock = threading.Lock()


def _path(out_dir: str | Path, run_id: str) -> Path:
    return Path(out_dir) / run_id / "row.json"


def save(out_dir: str | Path, run: Run) -> dict[str, Any]:
    """Build the run's row; save it unless the run is still going. Returns the row."""
    from harness.web.view import run_row

    row = run_row(run)
    if row["status"] != "running":
        p = _path(out_dir, run.run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": ROW_VERSION, "row": row}), encoding="utf-8")
        tmp.replace(p)  # atomic: a reader never sees half a file
    return row


def load(out_dir: str | Path, run_id: str) -> dict[str, Any] | None:
    """The saved row, or None when there is none, it can't be read, or it is from an older shape."""
    p = _path(out_dir, run_id)
    try:
        mtime = p.stat().st_mtime_ns
        with _memo_lock:
            hit = _memo.get(p)
        if hit and hit[0] == mtime:
            return hit[1]
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != ROW_VERSION:
        return None
    row = data.get("row")
    if not isinstance(row, dict):
        return None
    with _memo_lock:
        _memo[p] = (mtime, row)
    return row
