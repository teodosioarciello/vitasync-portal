from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    title: str
    document_type: str
    source_filename: str
    mime_type: str
    size_bytes: int
    document_date: date | None
    processing_status: str
    ai_status: str
    created_at: datetime
