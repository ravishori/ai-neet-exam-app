import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator


class StartIngestionJobRequest(BaseModel):
    """Start ingestion from a registered source or a guarded filesystem path.

    Modes (mutually exclusive):
    - ``source_document_id``: registry-authoritative path + academic mapping
    - ``file_path`` + ``chapter_code``: legacy path-based flow with auto-link
      to SourceDocument by checksum when a registered match exists
    """

    source_document_id: uuid.UUID | None = None
    file_path: str | None = Field(default=None, max_length=1000)
    chapter_code: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_request_mode(self) -> Self:
        has_id = self.source_document_id is not None
        has_path = bool(self.file_path and self.file_path.strip())
        if has_id and has_path:
            raise ValueError("Provide source_document_id or file_path, not both")
        if not has_id and not has_path:
            raise ValueError("Provide source_document_id or file_path")
        if has_path and not self.chapter_code:
            raise ValueError("chapter_code is required for path-based ingestion")
        if has_id and self.chapter_code:
            raise ValueError("chapter_code must not be supplied with source_document_id; the academic mapping is authoritative")
        return self


class DiscoverSourceDocumentsRequest(BaseModel):
    """Discovery always uses Settings.study_material_dir — no client root."""

    dry_run: bool = False
