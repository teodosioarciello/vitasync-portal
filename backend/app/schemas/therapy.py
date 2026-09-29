from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ALLOWED_THERAPY_STATUSES = {
    "active",
    "paused",
    "completed",
    "cancelled",
}

ALLOWED_THERAPY_FREQUENCIES = {
    "once_daily",
    "twice_daily",
    "three_times_daily",
    "four_times_daily",
    "every_other_day",
    "weekly",
    "as_needed",
    "custom",
}

ALLOWED_REMINDER_TYPES = {
    "medication",
    "appointment",
    "refill",
    "measurement",
    "other",
}

ALLOWED_REMINDER_STATUSES = {
    "pending",
    "done",
    "snoozed",
    "cancelled",
}


class MedicineBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    generic_name: str | None = Field(default=None, max_length=160)
    form: str | None = Field(default=None, max_length=64)
    strength: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class MedicineCreate(MedicineBase):
    patient_id: UUID


class MedicineOut(MedicineBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class MedicineUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    generic_name: str | None = Field(default=None, max_length=160)
    form: str | None = Field(default=None, max_length=64)
    strength: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class TherapyCreate(BaseModel):
    patient_id: UUID
    medicine_id: UUID
    status: str = "active"
    start_date: date | None = None
    end_date: date | None = None
    frequency: str = "once_daily"
    dose: str | None = Field(default=None, max_length=128)
    route: str | None = Field(default=None, max_length=64)
    instructions: str | None = None
    prescribed_by: str | None = Field(default=None, max_length=160)
    prescription_document_id: UUID | None = None
    notes: str | None = None


class TherapyUpdate(BaseModel):
    medicine_id: UUID | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    frequency: str | None = None
    dose: str | None = Field(default=None, max_length=128)
    route: str | None = Field(default=None, max_length=64)
    instructions: str | None = None
    prescribed_by: str | None = Field(default=None, max_length=160)
    prescription_document_id: UUID | None = None
    notes: str | None = None


class TherapyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    medicine_id: UUID
    medicine: MedicineOut | None = None
    status: str
    start_date: date | None
    end_date: date | None
    frequency: str
    dose: str | None
    route: str | None
    instructions: str | None
    prescribed_by: str | None
    prescription_document_id: UUID | None
    notes: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    patient_id: UUID
    therapy_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    reminder_type: str = "medication"
    scheduled_at: datetime
    status: str = "pending"
    recurrence_rule: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class ReminderUpdate(BaseModel):
    therapy_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    reminder_type: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = None
    recurrence_rule: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    therapy_id: UUID | None
    title: str
    reminder_type: str
    scheduled_at: datetime
    status: str
    recurrence_rule: str | None
    notes: str | None
    completed_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime