from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LabTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    patient_id: UUID
    test_code: str
    test_name_original: str
    test_name_normalized: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    reference_min: float | None
    reference_max: float | None
    reference_text: str | None
    flag: str | None
    method: str | None
    previous_value_numeric: float | None
    previous_value_text: str | None
    previous_date: date | None
    extracted_at: datetime
    confidence: float | None
    confirmed_by_user: bool
    user_corrected: bool
    notes: str | None
    created_at: datetime