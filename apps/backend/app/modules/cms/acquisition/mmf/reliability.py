"""Provider reliability metrics — no secrets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FailureClass = Literal[
    "EMPTY_RESPONSE",
    "INVALID_JSON",
    "TIMEOUT",
    "RATE_LIMIT",
    "PROVIDER_ERROR",
    "PARSER_ERROR",
    "UNKNOWN",
]


@dataclass
class ProviderReliabilityMetrics:
    provider: str
    requested: int = 0
    attempted: int = 0
    successful: int = 0
    empty_response: int = 0
    parse_failure: int = 0
    timeout: int = 0
    rate_limit: int = 0
    provider_error: int = 0
    terminal_failure: int = 0
    model: str = ""
    errors_sample: list[str] = field(default_factory=list)

    def record_attempt(self) -> None:
        self.attempted += 1

    def record_success(self, n: int = 1) -> None:
        self.successful += n

    def record_failure(self, kind: FailureClass, message: str | None = None) -> None:
        if kind == "EMPTY_RESPONSE":
            self.empty_response += 1
        elif kind in {"INVALID_JSON", "PARSER_ERROR"}:
            self.parse_failure += 1
        elif kind == "TIMEOUT":
            self.timeout += 1
        elif kind == "RATE_LIMIT":
            self.rate_limit += 1
        elif kind == "PROVIDER_ERROR":
            self.provider_error += 1
        if message and len(self.errors_sample) < 20:
            # Redact anything that looks like a secret
            msg = message[:200]
            low = msg.lower()
            if any(x in low for x in ("api_key", "authorization", "bearer ", "sk-")):
                msg = "***REDACTED***"
            self.errors_sample.append(msg)

    def record_terminal(self, slots: int = 1) -> None:
        self.terminal_failure += slots

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_provider_error(exc: BaseException | str) -> FailureClass:
    text = str(exc).lower()
    if not text.strip() or "expecting value: line 1 column 1" in text or text.strip() in {"", "empty", "empty_response"}:
        if "expecting value: line 1 column 1" in text or "empty" in text:
            return "EMPTY_RESPONSE"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    if "rate" in text and "limit" in text:
        return "RATE_LIMIT"
    if "expecting" in text or "json" in text or "parse" in text:
        return "INVALID_JSON"
    if "provider" in text or "http" in text or "api" in text or "status" in text:
        return "PROVIDER_ERROR"
    if not text.strip():
        return "EMPTY_RESPONSE"
    return "UNKNOWN"


def is_retryable(kind: FailureClass) -> bool:
    return kind in {"EMPTY_RESPONSE", "TIMEOUT", "RATE_LIMIT", "PROVIDER_ERROR"}


__all__ = [
    "FailureClass",
    "ProviderReliabilityMetrics",
    "classify_provider_error",
    "is_retryable",
]
