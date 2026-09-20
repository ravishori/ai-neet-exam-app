"""Structured logging with automatic redaction of sensitive fields."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|pwd|secret|token|otp|api[_-]?key|authorization|cookie|"
    r"session|refresh[_-]?token|access[_-]?token|jwt|private[_-]?key|credential)",
    re.IGNORECASE,
)

REDACTED = "[REDACTED]"


def redact_value(key: str, value: Any) -> Any:
    if SENSITIVE_KEY_PATTERN.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, str) and len(value) > 24 and ("Bearer " in value or value.count(".") == 2):
        # Likely JWT / bearer token embedded in a free-form string field.
        if "token" in key.lower() or "authorization" in key.lower():
            return REDACTED
    return value


def redact_event_dict(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(str(key), value) for key, value in event_dict.items()}


def configure_logging(environment: str) -> None:
    # Windows consoles default to cp1252; NCERT PDF text often includes Greek
    # symbols and other Unicode that must not crash structlog rendering.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_event_dict,
    ]

    if environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
