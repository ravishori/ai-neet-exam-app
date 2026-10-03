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


# Matches a credential-bearing query-string param (e.g. "...?key=AIza...",
# "&api_key=...", "&access_token=...") or an "Authorization: Bearer ..."
# header fragment embedded inside free-form text such as str(exc) on an
# httpx exception, which carries its triggering request's full URL and is
# not caught by redact_event_dict (that only inspects dict keys, not the
# contents of string values). Value characters stop at whitespace/&/,/;/)/
# quotes so redaction doesn't eat unrelated trailing diagnostic text — except
# when the value itself is quoted (e.g. dict/repr-style
# "'x-goog-api-key': 'AIza...'"), in which case the whole quoted span is
# matched instead, since a bare leading quote would otherwise block any
# match at all.
_CREDENTIAL_VALUE = r"""(?:'[^']*'|"[^"]*"|[^\s&,;)"']+)"""
_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b((?:api[_-]?key|access[_-]?token|token|secret|key)=)" + _CREDENTIAL_VALUE
)
_AUTH_HEADER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)" + _CREDENTIAL_VALUE)
# Header-text form of our own Gemini auth header (gemini_provider.py /
# gemini_batch.py send it as `x-goog-api-key`), e.g. "x-goog-api-key: AIza...".
# Not currently emitted by any str(exc) path (httpx exceptions don't embed
# request headers), but kept in sync with whatever header name actually
# carries the credential so a future diagnostic/debug path can't bypass it.
# Case-insensitive, tolerant of whitespace around the ':' or '=' delimiter.
_GOOG_API_KEY_HEADER_PATTERN = re.compile(
    r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*)" + _CREDENTIAL_VALUE
)


def sanitize_error_text(text: str | None, *, limit: int = 500) -> str | None:
    """Strip credential-bearing URL params / auth headers from raw exception
    text before it is logged or persisted. Use at any site that logs
    str(exc) on an exception not already normalized into ProviderError."""
    if text is None:
        return None
    cleaned = _URL_CREDENTIAL_PATTERN.sub(r"\1" + REDACTED, text)
    cleaned = _AUTH_HEADER_PATTERN.sub(r"\1" + REDACTED, cleaned)
    cleaned = _GOOG_API_KEY_HEADER_PATTERN.sub(r"\1" + REDACTED, cleaned)
    return cleaned[:limit]


def configure_logging(environment: str) -> None:
    # Windows consoles default to cp1252; NCERT PDF text often includes Greek
    # symbols and other Unicode that must not crash structlog rendering.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    # httpx (and httpcore underneath it) log via the stdlib `logging` module,
    # not structlog — their "HTTP Request: {method} {url} ..." INFO line
    # propagates straight to the root handler above, bypassing
    # redact_event_dict entirely. Any outbound call that puts a credential in
    # the URL (query-string API keys) would otherwise leak it verbatim
    # regardless of how carefully application-level logger.* calls are
    # written. Keep warnings/errors visible; drop routine request logging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

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
