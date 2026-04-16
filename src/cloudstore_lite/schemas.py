from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ObjectMetadata(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime


class DeleteResponse(BaseModel):
    status: str


class HealthStatus(BaseModel):
    status: str


class SignedURLRequest(BaseModel):
    expires_in_seconds: int | None = Field(default=None, ge=60, le=86400)


class SignedURLResponse(BaseModel):
    url: str
    expires_at: datetime
