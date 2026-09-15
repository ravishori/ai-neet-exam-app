"""PASTQ-IMPORT-001 — past-question-paper intake (acquisition only).

Reuses cms.pyq extraction. Never treats PastQuestionPapers as NCERT.
Never publishes. Never mutates source files.
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_SOURCE_ROOT",
    "inventory_source_root",
    "run_pastq_pipeline",
]

DEFAULT_SOURCE_ROOT = r"D:\ravishori\AI Neet Exam App\PastQuestionPapers"
