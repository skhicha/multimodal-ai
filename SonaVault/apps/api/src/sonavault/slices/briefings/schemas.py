import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BriefingSynthesizeRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000)
    sanctuary_scope: str | None = None
    max_evidence_chunks: int = Field(default=8, ge=1, le=20)


class BriefingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    prompt: str
    sanctuary_scope: str | None
    markdown_body: str
    cited_sha256s: list[str]
    model_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BriefingListItem(BaseModel):
    id: uuid.UUID
    prompt: str
    sanctuary_scope: str | None
    model_id: str
    created_at: datetime
    excerpt: str

    model_config = {"from_attributes": True}


class BriefingExportResponse(BaseModel):
    briefing_id: uuid.UUID
    dossier_markdown: str
    sha256_digest: str
    created_at: datetime
