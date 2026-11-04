"""Every piece of text sent to a model lives in prompts/ as Markdown; this is the only way code reads it."""

from __future__ import annotations

import os
from pathlib import Path

PROMPTS_DIR = Path(os.environ.get("HARNESS_PROMPTS_DIR", Path(__file__).resolve().parents[1] / "prompts"))


def path(name: str) -> Path:
    """prompts/<name>.md, e.g. path("agent/system")."""
    return PROMPTS_DIR / f"{name}.md"


def load(name: str, **values: object) -> str:
    """Read prompts/<name>.md and fill {placeholders} from values (str.format)."""
    text = path(name).read_text(encoding="utf-8")
    return text.format(**values) if values else text
