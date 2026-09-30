from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_authorized_patient
from app.db.models import Document, User
from app.db.therapy_models import Medicine, Reminder, Therapy


def get_authorized_medicine(
    medicine_id: UUID,
    user: User,
    db: Session,
    required_permission: str = "read",
) -> Medicine:
    medicine = db.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicinale non trovato.",
        )

    get_authorized_patient(
        medicine.patient_id,
        user,
        db,
        required_permission=required_permission,
    )
    return medicine


def get_authorized_therapy(
    therapy_id: UUID,
    user: User,
    db: Session,
    required_permission: str = "read",
) -> Therapy:
    therapy = db.get(Therapy, therapy_id)
    if not therapy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terapia non trovata.",
        )

    get_authorized_patient(
        therapy.patient_id,
        user,
        db,
        required_permission=required_permission,
    )
    return therapy


def get_authorized_reminder(
    reminder_id: UUID,
    user: User,
    db: Session,
    required_permission: str = "read",
) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promemoria non trovato.",
        )

    get_authorized_patient(
        reminder.patient_id,
        user,
        db,
        required_permission=required_permission,
    )
    return reminder


def validate_medicine_for_patient(
    medicine_id: UUID,
    patient_id: UUID,
    db: Session,
) -> Medicine:
    medicine = db.get(Medicine, medicine_id)
    if not medicine or medicine.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Medicinale non valido per questo paziente.",
        )
    return medicine


def validate_document_for_patient(
    document_id: UUID,
    patient_id: UUID,
    db: Session,
) -> Document:
    document = db.get(Document, document_id)
    if not document or document.patient_id != patient_id or document.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documento non disponibile perche' nel cestino o non valido per questo paziente.",
        )
    return document


def validate_therapy_dates(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date non puo' essere precedente a start_date.",
        )


def ensure_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)