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


class LabTestUpdate(BaseModel):
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reference_min: float | None = None
    reference_max: float | None = None
    reference_text: str | None = None
    notes: str | None = None
    confirmed: bool = False


class ConfirmAllResponse(BaseModel):
    updated_count: int
    detail: str


class TrendPoint(BaseModel):
    date: date | None
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    reference_min: float | None
    reference_max: float | None
    flag: str | None
    document_id: UUID
    document_title: str
    test_name_normalized: str
    confirmed_by_user: bool
    user_corrected: bool
    created_at: datetime


class TrendResponse(BaseModel):
    patient_id: UUID
    test_code: str
    test_name_normalized: str | None
    unit: str | None
    points: list[TrendPoint]


class LabTestCodeSummary(BaseModel):
    test_code: str
    test_name_normalized: str
    last_value_numeric: float | None
    last_value_text: str | None
    last_unit: str | None
    last_flag: str | None
    last_date: date | None
    points_count: int