from __future__ import annotations

from pydantic import BaseModel, Field


class UnlinkRequest(BaseModel):
    phone_e164: str = Field(min_length=1, max_length=20)
