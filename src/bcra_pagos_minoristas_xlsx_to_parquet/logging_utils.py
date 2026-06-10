"""Logging helpers used across all pipeline stages."""

from __future__ import annotations

import json
import logging
import time
from functools import wraps
from typing import Any


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured *event* with the given keyword fields.

    ``duration_ms`` is stripped before serialisation so it is logged as a
    top-level field rather than buried inside an embedded ``{"event": ...}``
    wrapper.
    """
    duration_ms = fields.pop("duration_ms", 0)
    payload: dict[str, Any] = {"event": event}
    payload.update(fields)
    if duration_ms:
        payload["duration_ms"] = duration_ms
    logger.info(json.dumps(payload, default=str, ensure_ascii=True))


def timed(func):
    """Decorator that measures *func* execution time in milliseconds.

    The wrapped function is expected to accept (and optionally return) a
    ``duration_ms`` key when the result is a ``dict`` -- the decorator
    updates this key automatically so callers do not need to track it.

    Usage::

        @timed
        def my_stage(...):
            ...
            return {"status": "ok"}

    Returns ``{"status": "ok", "duration_ms": 42}``
    """

    @wraps(func)
    def wrapper(*args, _timer=None, **kwargs):
        if _timer is None:
            _timer = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = round((time.perf_counter() - _timer) * 1000, 2)
        if isinstance(result, dict):
            result["duration_ms"] = duration_ms
        return result

    return wrapper
