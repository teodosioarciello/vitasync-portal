"""
Sprint B Step 4A.

Servizio per notificare promemoria scaduti.

Canali supportati:
- console: stampa a log/stdout, nessuna email reale;
- smtp: invio email via SMTP configurato tramite env var.

Env var principali:
- NOTIFICATIONS_ENABLED=true|false
- NOTIFICATION_CHANNEL=console|smtp
- PUBLIC_APP_URL=http://localhost:3001
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
- SMTP_STARTTLS=true|false
- SMTP_SSL=true|false
- SMTP_TIMEOUT_SECONDS=30
"""

import html
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Patient, User
from app.db.notification_models import NotificationLog
from app.db.therapy_models import Reminder

logger = logging.getLogger(__name__)

EVENT_REMINDER_DUE = "reminder_due"

STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

CHANNEL_CONSOLE = "console"
CHANNEL_SMTP = "smtp"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    return raw.strip().lower() in {"1", "true", "yes", "on"}


def notifications_enabled() -> bool:
    return _env_bool("NOTIFICATIONS_ENABLED", True)


def get_channel() -> str:
    channel = os.getenv("NOTIFICATION_CHANNEL", CHANNEL_CONSOLE).strip().lower()

    if channel not in {CHANNEL_CONSOLE, CHANNEL_SMTP}:
        logger.warning("Canale notifiche non valido: %s. Uso console.", channel)
        return CHANNEL_CONSOLE

    return channel


def public_app_url() -> str:
    return os.getenv("PUBLIC_APP_URL", "http://localhost:3001").rstrip("/")


def _get_reminder_recipient(db: Session, reminder: Reminder) -> tuple[User | None, Patient | None, str | None]:
    patient = db.get(Patient, reminder.patient_id) if reminder.patient_id else None
    user = db.get(User, reminder.created_by_user_id) if reminder.created_by_user_id else None

    if not user:
        return None, patient, "Utente creatore del promemoria non trovato."

    if not user.email:
        return user, patient, "Utente destinatario senza email."

    return user, patient, None


def build_reminder_due_message(reminder: Reminder, patient: Patient | None, user: User) -> tuple[str, str, str]:
    title = reminder.title or "Promemoria"
    safe_title = html.escape(title)
    safe_type = html.escape(reminder.reminder_type or "promemoria")
    patient_name = html.escape(patient.display_name if patient else "paziente")
    link = html.escape(f"{public_app_url()}/reminders")

    subject = f"Promemoria VitaSync: {title}"

    body_text = (
        f"Ciao {user.full_name or user.username},\n\n"
        f"Un promemoria e' scaduto o risulta pendente.\n\n"
        f"Titolo: {title}\n"
        f"Tipo: {reminder.reminder_type}\n"
        f"Paziente: {patient.display_name if patient else 'n/d'}\n"
        f"Scheduled: {reminder.scheduled_at.isoformat()}\n\n"
        f"Apri il portale: {public_app_url()}/reminders\n\n"
        f"Questo messaggio e' generato automaticamente da VitaSync Portal.\n"
    )

    body_html = f"""
<!doctype html>
<html lang="it">
  <body style="font-family: Arial, sans-serif; line-height: 1.4;">
    <p>Ciao <strong>{html.escape(user.full_name or user.username)}</strong>,</p>
    <p>Un promemoria e' scaduto o risulta pendente.</p>
    <ul>
      <li><strong>Titolo:</strong> {safe_title}</li>
      <li><strong>Tipo:</strong> {safe_type}</li>
      <li><strong>Paziente:</strong> {patient_name}</li>
      <li><strong>Scheduled:</strong> {html.escape(reminder.scheduled_at.isoformat())}</li>
    </ul>
    <p><a href="{link}">Apri promemoria su VitaSync Portal</a></p>
    <p style="font-size: 12px; color: #64748b;">
      Questo messaggio e' generato automaticamente da VitaSync Portal.
    </p>
  </body>
</html>
"""

    return subject, body_text, body_html


def _send_smtp_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str,
) -> None:
    host = os.getenv("SMTP_HOST")

    if not host:
        raise RuntimeError("SMTP_HOST non configurato.")

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or user or "noreply@vitasync.local"
    use_ssl = _env_bool("SMTP_SSL", False)
    starttls = _env_bool("SMTP_STARTTLS", not use_ssl and port == 587)
    timeout = int(os.getenv("SMTP_TIMEOUT_SECONDS", "30"))

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)

    try:
        if starttls and not use_ssl:
            server.starttls()

        if user:
            server.login(user, password or "")

        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            pass


def _create_notification_log(
    db: Session,
    *,
    reminder: Reminder | None,
    patient: Patient | None,
    user: User | None,
    channel: str,
    event: str,
    status: str,
    recipient: str | None,
    subject: str | None,
    error: str | None,
    scheduled_for: datetime,
    sent_at: datetime | None,
    metadata: dict | None = None,
) -> tuple[NotificationLog | None, str | None]:
    log = NotificationLog(
        reminder_id=reminder.id if reminder else None,
        patient_id=patient.id if patient else None,
        user_id=user.id if user else None,
        channel=channel,
        event=event,
        status=status,
        recipient=recipient,
        subject=subject,
        error=error,
        scheduled_for=scheduled_for,
        sent_at=sent_at,
        metadata_json=metadata or {},
    )

    db.add(log)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Notificazione duplicata o vincolo violato: %s", exc)
        return None, "Notificazione gia' registrata come inviata."
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Creazione notification_log fallita")
        return None, str(exc)

    db.refresh(log)
    return log, None


def dispatch_reminder_due(
    db: Session,
    reminder: Reminder,
    *,
    channel: str | None = None,
    dry_run: bool = False,
) -> str:
    """
    Invia/registrar una notifica reminder_due.

    Ritorna lo status: sent | failed | skipped.
    In dry-run non crea log e non invia nulla.
    """
    if dry_run:
        return STATUS_SKIPPED

    channel = channel or get_channel()
    user, patient, recipient_error = _get_reminder_recipient(db, reminder)

    metadata = {
        "reminder_id": str(reminder.id),
        "patient_id": str(reminder.patient_id),
        "reminder_type": reminder.reminder_type,
        "scheduled_at": reminder.scheduled_at.isoformat(),
    }

    if recipient_error or not user:
        _create_notification_log(
            db,
            reminder=reminder,
            patient=patient,
            user=user,
            channel=channel,
            event=EVENT_REMINDER_DUE,
            status=STATUS_SKIPPED,
            recipient=None,
            subject=None,
            error=recipient_error or "Destinatario non disponibile.",
            scheduled_for=reminder.scheduled_at,
            sent_at=None,
            metadata=metadata,
        )
        return STATUS_SKIPPED

    subject, body_text, body_html = build_reminder_due_message(reminder, patient, user)
    recipient = user.email

    if channel == CHANNEL_CONSOLE:
        logger.info(
            "NOTIFICA CONSOLE reminder_due id=%s recipient=%s subject=%s",
            reminder.id,
            recipient,
            subject,
        )
        print("---- NOTIFICA CONSOLE ----")
        print(f"reminder_id: {reminder.id}")
        print(f"recipient: {recipient}")
        print(f"subject: {subject}")
        print(body_text)
        print("--------------------------")

        _create_notification_log(
            db,
            reminder=reminder,
            patient=patient,
            user=user,
            channel=CHANNEL_CONSOLE,
            event=EVENT_REMINDER_DUE,
            status=STATUS_SENT,
            recipient=recipient,
            subject=subject,
            error=None,
            scheduled_for=reminder.scheduled_at,
            sent_at=_utcnow(),
            metadata=metadata,
        )
        return STATUS_SENT

    if channel == CHANNEL_SMTP:
        if not notifications_enabled():
            _create_notification_log(
                db,
                reminder=reminder,
                patient=patient,
                user=user,
                channel=CHANNEL_SMTP,
                event=EVENT_REMINDER_DUE,
                status=STATUS_SKIPPED,
                recipient=recipient,
                subject=subject,
                error="NOTIFICATIONS_ENABLED non e' true.",
                scheduled_for=reminder.scheduled_at,
                sent_at=None,
                metadata=metadata,
            )
            return STATUS_SKIPPED

        try:
            _send_smtp_email(
                to=recipient,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Invio SMTP promemoria fallito per reminder %s", reminder.id)

            _create_notification_log(
                db,
                reminder=reminder,
                patient=patient,
                user=user,
                channel=CHANNEL_SMTP,
                event=EVENT_REMINDER_DUE,
                status=STATUS_FAILED,
                recipient=recipient,
                subject=subject,
                error=str(exc),
                scheduled_for=reminder.scheduled_at,
                sent_at=None,
                metadata=metadata,
            )
            return STATUS_FAILED

        _create_notification_log(
            db,
            reminder=reminder,
            patient=patient,
            user=user,
            channel=CHANNEL_SMTP,
            event=EVENT_REMINDER_DUE,
            status=STATUS_SENT,
            recipient=recipient,
            subject=subject,
            error=None,
            scheduled_for=reminder.scheduled_at,
            sent_at=_utcnow(),
            metadata=metadata,
        )
        return STATUS_SENT

    _create_notification_log(
        db,
        reminder=reminder,
        patient=patient,
        user=user,
        channel=channel,
        event=EVENT_REMINDER_DUE,
        status=STATUS_FAILED,
        recipient=recipient,
        subject=subject,
        error=f"Canale non supportato: {channel}",
        scheduled_for=reminder.scheduled_at,
        sent_at=None,
        metadata=metadata,
    )
    return STATUS_FAILED


def collect_due_reminders(
    db: Session,
    now: datetime | None = None,
    limit: int = 100,
    only_reminder_ids: list[str] | None = None,
) -> list[Reminder]:
    now = now or _utcnow()

    query = (
        db.query(Reminder)
        .outerjoin(
            NotificationLog,
            and_(
                NotificationLog.reminder_id == Reminder.id,
                NotificationLog.event == EVENT_REMINDER_DUE,
                NotificationLog.status == STATUS_SENT,
            ),
        )
        .filter(
            Reminder.status == "pending",
            Reminder.scheduled_at <= now,
            NotificationLog.id.is_(None),
        )
        .order_by(Reminder.scheduled_at.asc())
    )

    if only_reminder_ids is not None:
        if not only_reminder_ids:
            return []

        uuid_ids = [UUID(str(x)) for x in only_reminder_ids]
        query = query.filter(Reminder.id.in_(uuid_ids))

    return query.limit(limit).all()


def send_due_reminders(
    db: Session,
    now: datetime | None = None,
    dry_run: bool = False,
    limit: int = 100,
    channel_override: str | None = None,
    only_reminder_ids: list[str] | None = None,
) -> dict:
    now = now or _utcnow()
    channel = channel_override or get_channel()

    reminders = collect_due_reminders(
        db,
        now=now,
        limit=limit,
        only_reminder_ids=only_reminder_ids,
    )

    summary = {
        "channel": channel,
        "dry_run": dry_run,
        "candidates": len(reminders),
        "sent": 0,
        "failed": 0,
        "skipped": 0,
    }

    for reminder in reminders:
        if dry_run:
            print(
                f"DRY-RUN: promemoria {reminder.id} sarebbe notificato "
                f"(scheduled_at={reminder.scheduled_at.isoformat()}, title={reminder.title!r})"
            )
            summary["skipped"] += 1
            continue

        status = dispatch_reminder_due(
            db,
            reminder,
            channel=channel,
            dry_run=False,
        )

        if status == STATUS_SENT:
            summary["sent"] += 1
        elif status == STATUS_FAILED:
            summary["failed"] += 1
        else:
            summary["skipped"] += 1

    return summary