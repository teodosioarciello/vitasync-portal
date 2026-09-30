from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.documents import get_authorized_patient
from app.db.models import User
from app.db.therapy_models import Reminder, Therapy
from app.deps import get_current_user, get_db
from app.schemas.therapy import (
    ALLOWED_REMINDER_STATUSES,
    ALLOWED_REMINDER_TYPES,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
)
from app.services.audit_identity import mark_audit_user
from app.services.family import ensure_family_and_self_patient
from app.services.therapy import (
    ensure_tz,
    get_authorized_reminder,
)

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderOut])
def list_reminders(
    patient_id: UUID | None = Query(None),
    reminder_status: str | None = Query(None, alias="status"),
    from_dt: datetime | None = Query(None),
    to_dt: datetime | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
    else:
        patient = get_authorized_patient(
            patient_id, current_user, db, required_permission="read"
        )

    if reminder_status is not None and reminder_status not in ALLOWED_REMINDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stato promemoria non valido.",
        )

    from_dt = ensure_tz(from_dt)
    to_dt = ensure_tz(to_dt)

    query = db.query(Reminder).filter(Reminder.patient_id == patient.id)

    if reminder_status is not None:
        query = query.filter(Reminder.status == reminder_status)

    if from_dt is not None:
        query = query.filter(Reminder.scheduled_at >= from_dt)

    if to_dt is not None:
        query = query.filter(Reminder.scheduled_at <= to_dt)

    rows = query.order_by(Reminder.scheduled_at.asc()).limit(200).all()
    return [ReminderOut.model_validate(row) for row in rows]


@router.post("", response_model=ReminderOut)
def create_reminder(
    request: Request,
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    patient = get_authorized_patient(
        payload.patient_id, current_user, db, required_permission="write"
    )

    if payload.reminder_type not in ALLOWED_REMINDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo promemoria non valido.",
        )

    if payload.status not in ALLOWED_REMINDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stato promemoria non valido.",
        )

    if payload.therapy_id is not None:
        therapy = db.get(Therapy, payload.therapy_id)
        if not therapy or therapy.patient_id != patient.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Terapia non valida per questo paziente.",
            )

    scheduled_at = ensure_tz(payload.scheduled_at)
    if scheduled_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_at obbligatorio.",
        )

    completed_at = None
    if payload.status == "done":
        completed_at = datetime.now(timezone.utc)

    title = payload.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Titolo promemoria non valido.",
        )

    reminder = Reminder(
        patient_id=patient.id,
        therapy_id=payload.therapy_id,
        title=title,
        reminder_type=payload.reminder_type,
        scheduled_at=scheduled_at,
        status=payload.status,
        recurrence_rule=payload.recurrence_rule,
        notes=payload.notes,
        completed_at=completed_at,
        created_by_user_id=current_user.id,
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return ReminderOut.model_validate(reminder)


@router.get("/{reminder_id}", response_model=ReminderOut)
def get_reminder(
    reminder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reminder = get_authorized_reminder(
        reminder_id, current_user, db, required_permission="read"
    )
    return ReminderOut.model_validate(reminder)


@router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    request: Request,
    reminder_id: UUID,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    reminder = get_authorized_reminder(
        reminder_id, current_user, db, required_permission="write"
    )

    data = payload.model_dump(exclude_unset=True)

    if "therapy_id" in data and data["therapy_id"] is not None:
        therapy = db.get(Therapy, data["therapy_id"])
        if not therapy or therapy.patient_id != reminder.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Terapia non valida per questo paziente.",
            )

    if "reminder_type" in data:
        if data["reminder_type"] not in ALLOWED_REMINDER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo promemoria non valido.",
            )

    if "status" in data:
        if data["status"] not in ALLOWED_REMINDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stato promemoria non valido.",
            )

    if "title" in data:
        if data["title"] is None or not str(data["title"]).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Titolo promemoria non valido.",
            )
        data["title"] = str(data["title"]).strip()

    if "scheduled_at" in data:
        data["scheduled_at"] = ensure_tz(data["scheduled_at"])

    old_status = reminder.status

    for key, value in data.items():
        setattr(reminder, key, value)

    if "status" in data:
        new_status = data["status"]
        if new_status == "done" and old_status != "done":
            reminder.completed_at = datetime.now(timezone.utc)
        elif new_status != "done" and old_status == "done":
            reminder.completed_at = None

    db.commit()
    db.refresh(reminder)

    return ReminderOut.model_validate(reminder)