"""Safety guards for MMF — fail closed."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.modules.cms.acquisition.mmf.config import redact_secrets


class GuardError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_source_sha(path: Path, expected: str) -> str:
    if not path.exists():
        raise GuardError("MISSING_SOURCE", f"source fixture missing: {path}")
    actual = sha256_file(path)
    if actual != expected.lower():
        raise GuardError("SOURCE_SHA_MISMATCH", f"expected {expected}, got {actual}")
    return actual


def assert_no_live_generation(live_enabled: bool) -> None:
    if live_enabled:
        raise GuardError(
            "LIVE_GENERATION_BLOCKED",
            "Live provider generation is not authorized in this infrastructure milestone",
        )


def assert_no_content_workflow_import(flag: bool) -> None:
    if flag:
        raise GuardError(
            "CONTENTITEM_IMPORT_BLOCKED",
            "Candidate-to-ContentItem import requires a separate authorization gate",
        )


def assert_report_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure reports do not embed secrets."""
    redacted = redact_secrets(payload)
    blob = str(redacted).lower()
    for needle in ("sk-ant-", "sk-proj-", "api_key=", "bearer "):
        if needle in blob:
            raise GuardError("SECRET_LEAK_RISK", f"report contains banned pattern: {needle}")
    return redacted
