"""Multi-Model Question Candidate Factory (MMF) — acquisition infrastructure.

Candidates are file-based artifacts. They are NOT ContentItems.
Provider adapters must never call ContentWorkflowService.
Live provider HTTP is disabled unless an explicit future command enables it.
"""

from app.modules.cms.acquisition.mmf.schemas import (
    CANDIDATE_SCHEMA_VERSION,
    CandidateRecord,
    CandidateStatus,
    GenerationBatch,
    GenerationBatchStatus,
)

__all__ = [
    "CANDIDATE_SCHEMA_VERSION",
    "CandidateRecord",
    "CandidateStatus",
    "GenerationBatch",
    "GenerationBatchStatus",
]
