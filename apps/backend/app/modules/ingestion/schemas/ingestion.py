from pydantic import BaseModel, Field


class StartIngestionJobRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1000)
    chapter_code: str = Field(min_length=1, max_length=80)
