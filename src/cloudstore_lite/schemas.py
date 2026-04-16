from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ObjectMetadata(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime


class HealthStatus(BaseModel):
    status: str

