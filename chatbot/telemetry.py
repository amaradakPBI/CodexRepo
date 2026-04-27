from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)")


def sanitize_text(value: str) -> str:
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    return value


def build_logger(log_file: Path, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("chatbot")
    if logger.handlers:
        logger.setLevel(level)
        return logger
    logger.setLevel(level)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)
    return logger


def log_event(logger: logging.Logger, event: str, payload: dict[str, Any]) -> None:
    sanitized = {
        key: sanitize_text(value) if isinstance(value, str) else value
        for key, value in payload.items()
    }
    logger.info(json.dumps({"event": event, **sanitized}, ensure_ascii=True))
