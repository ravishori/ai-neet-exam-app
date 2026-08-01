"""AI-assist pass for submitted content — see ADR-0004 / ECAEP spec.

Real grammar/NCERT-alignment/duplicate-detection checks land in Sprint 5
once the AI Gateway exists. Until then this is a pass-through stub that
still writes a report shaped the same way the real Evaluator agent will,
so the workflow and UI never need to change when it's wired up for real.
"""

from datetime import UTC, datetime


def run_ai_check(*, content_type: str, body: dict) -> dict:
    return {
        "status": "skipped",
        "reason": "AI Gateway not yet wired up (Sprint 5) — content proceeds to human review unchecked.",
        "flags": [],
        "similarity_matches": [],
        "confidence": None,
        "checked_at": datetime.now(UTC).isoformat(),
    }
