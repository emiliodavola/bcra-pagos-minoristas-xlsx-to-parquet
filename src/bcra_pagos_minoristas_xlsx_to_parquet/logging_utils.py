from __future__ import annotations

import json
import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str, ensure_ascii=True))
