"""Local runner: `python -m agent.local <payload.json>` calls the same handle() as /invocations.

The CLI reads the response from result.json in the archive, never from stdout. Exit 0 means the run
completed (with any status); non-zero means the process crashed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agent.handler import handle


def main(argv: list[str]) -> int:
    payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    handle(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
