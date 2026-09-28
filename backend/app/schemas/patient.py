from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    display_name: str
    birth_date: date | None
    sex: str | None
    height_cm: float | None
    relationship_to_owner: str
    is_minor: bool
    consent_status: str