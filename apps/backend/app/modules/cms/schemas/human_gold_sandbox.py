"""Pydantic schemas for Human Gold Review Sandbox API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HumanReviewStatus = Literal["PENDING", "DRAFT", "COMPLETE"]
SessionStatus = Literal["ACTIVE", "COMPLETED", "EXPIRED", "DELETED", "CANCELLED"]


class HumanGoldReviewSaveRequest(BaseModel):
    human_stem: str | None = None
    human_option_a: str | None = Field(None, alias="human_option_A")
    human_option_b: str | None = Field(None, alias="human_option_B")
    human_option_c: str | None = Field(None, alias="human_option_C")
    human_option_d: str | None = Field(None, alias="human_option_D")
    human_answer: str | None = None
    human_explanation: str | None = None
    human_ncert_support: str | None = None
    human_ambiguity: str | None = None
    human_duplicate: str | None = None
    human_difficulty: str | None = None
    human_neet_suitability: str | None = None
    human_overall: str | None = None
    reviewer_notes: str | None = None
    mark_complete: bool = False

    model_config = {"populate_by_name": True}


class SessionCreateRequest(BaseModel):
    session_name: str = Field(min_length=1, max_length=200)


class ImportConfirmRequest(BaseModel):
    upload_id: str
    session_name: str = Field(min_length=1, max_length=200)
