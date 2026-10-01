"""
Sprint B Step 4C.

Endpoint read-only per elencare le notifiche registrate per l'utente corrente.

Questo modulo NON invia notifiche.
NON abilita SMTP.
NON elimina dati.
Legge soltanto notification_logs.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps import get_current_user

from app.db.notification_models import NotificationLog

router = APIRouter()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("")
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    event: str | None = Query(None),
    channel: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Elenca le notifiche dell'utente corrente.

    Filtri opzionali:
    - status: sent | failed | skipped
    - event: reminder_due
    - channel: console | smtp
    """
    query = db.query(NotificationLog).filter(
        NotificationLog.user_id == current_user.id
    )

    if status:
        query = query.filter(NotificationLog.status == status)

    if event:
        query = query.filter(NotificationLog.event == event)

    if channel:
        query = query.filter(NotificationLog.channel == channel)

    logs = (
        query
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(log.id),
            "reminder_id": str(log.reminder_id) if log.reminder_id else None,
            "patient_id": str(log.patient_id) if log.patient_id else None,
            "user_id": str(log.user_id) if log.user_id else None,
            "channel": log.channel,
            "event": log.event,
            "status": log.status,
            "recipient": log.recipient,
            "subject": log.subject,
            "error": log.error,
            "scheduled_for": _iso(log.scheduled_for),
            "sent_at": _iso(log.sent_at),
            "created_at": _iso(log.created_at),
            "metadata_json": log.metadata_json or {},
        }
        for log in logs
    ]