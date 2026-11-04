"""Module-level run context, visible from Strands' tool threads (design: Run context)."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_ctx: dict[str, Any] = {}


def set_context(values: dict[str, Any]) -> None:
    with _lock:
        _ctx.clear()
        _ctx.update(values)


def update(**values: Any) -> None:
    with _lock:
        _ctx.update(values)


def get(key: str, default: Any = None) -> Any:
    with _lock:
        return _ctx.get(key, default)


def snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_ctx)
