"""
Sprint B Step 4A.

Test deterministico per notifiche promemoria scaduti.

Crea:
- promemoria pendente scaduto;
- promemoria pendente futuro;
- promemoria completato scaduto.

Esegue send_due_reminders con canale console e only_reminder_ids.

Verifica:
- solo il promemoria pendente scaduto viene notificato;
- il secondo run non duplica;
- il promemoria futuro non viene notificato;
- il promemoria completato non viene notificato;
- viene creato notification_log status=sent.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import or_

from app.db.models import User
from app.db.notification_models import NotificationLog
from app.db.session import SessionLocal
from app.db.therapy_models import Reminder
from app.services.family import ensure_family_and_self_patient
from app.services.reminder_notifications import send_due_reminders

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
TITLE_PREFIX = "TEST B step4 notification "
NOTES_MARKER = "b-step4-notification-test"

failures: list[str] = []

past_id: str | None = None
future_id: str | None = None
completed_id: str | None = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


def cleanup_previous(db) -> None:
    previous = (
        db.query(Reminder)
        .filter(
            or_(
                Reminder.title.startswith(TITLE_PREFIX),
                Reminder.notes == NOTES_MARKER,
            )
        )
        .all()
    )

    previous_ids = [str(r.id) for r in previous]

    if previous_ids:
        db.query(NotificationLog).filter(
            NotificationLog.reminder_id.in_([UUID(x) for x in previous_ids])
        ).delete(synchronize_session=False)

    for reminder in previous:
        db.delete(reminder)

    db.commit()


def make_reminder(
    db,
    user: User,
    patient,
    suffix: str,
    scheduled_at: datetime,
    status: str,
):
    reminder = Reminder(
        patient_id=patient.id,
        therapy_id=None,
        title=f"{TITLE_PREFIX}{suffix} {RUN_ID}",
        reminder_type="medication",
        scheduled_at=scheduled_at,
        status=status,
        notes=NOTES_MARKER,
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
        created_by_user_id=user.id,
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return reminder


try:
    db = SessionLocal()

    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            raise RuntimeError("Nessun utente nel DB. Registra prima un account dal frontend.")

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        cleanup_previous(db)

        now = datetime.now(timezone.utc)

        past_reminder = make_reminder(
            db,
            user,
            patient,
            suffix="past",
            scheduled_at=now - timedelta(hours=1),
            status="pending",
        )

        future_reminder = make_reminder(
            db,
            user,
            patient,
            suffix="future",
            scheduled_at=now + timedelta(hours=1),
            status="pending",
        )

        completed_reminder = make_reminder(
            db,
            user,
            patient,
            suffix="completed",
            scheduled_at=now - timedelta(hours=2),
            status="completed",
        )

        past_id = str(past_reminder.id)
        future_id = str(future_reminder.id)
        completed_id = str(completed_reminder.id)

        print("Setup creato:")
        print(f"  past_reminder_id={past_id}")
        print(f"  future_reminder_id={future_id}")
        print(f"  completed_reminder_id={completed_id}")
        print()

        # 1. Dry-run: non deve creare log
        summary_dry = send_due_reminders(
            db,
            now=now,
            dry_run=True,
            limit=10,
            channel_override="console",
            only_reminder_ids=[past_id, future_id, completed_id],
        )

        check("dry-run candidati = 1", summary_dry["candidates"] == 1, f"summary={summary_dry}")

        dry_logs = (
            db.query(NotificationLog)
            .filter(NotificationLog.reminder_id.in_([UUID(past_id), UUID(future_id), UUID(completed_id)]))
            .count()
        )

        check("dry-run nessun log creato", dry_logs == 0, f"dry_logs={dry_logs}")

        # 2. Primo run reale
        summary_first = send_due_reminders(
            db,
            now=now,
            dry_run=False,
            limit=10,
            channel_override="console",
            only_reminder_ids=[past_id, future_id, completed_id],
        )

        check("primo run candidati = 1", summary_first["candidates"] == 1, f"summary={summary_first}")
        check("primo run sent = 1", summary_first["sent"] == 1, f"summary={summary_first}")
        check("primo run failed = 0", summary_first["failed"] == 0, f"summary={summary_first}")

        db.expire_all()

        past_logs = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.reminder_id == UUID(past_id),
                NotificationLog.event == "reminder_due",
                NotificationLog.status == "sent",
            )
            .all()
        )

        future_logs = (
            db.query(NotificationLog)
            .filter(NotificationLog.reminder_id == UUID(future_id))
            .count()
        )

        completed_logs = (
            db.query(NotificationLog)
            .filter(NotificationLog.reminder_id == UUID(completed_id))
            .count()
        )

        check("past ha 1 log sent", len(past_logs) == 1, f"count={len(past_logs)}")
        check("future nessun log", future_logs == 0, f"count={future_logs}")
        check("completed nessun log", completed_logs == 0, f"count={completed_logs}")

        if past_logs:
            log = past_logs[0]
            print()
            print("Notification log trovato:")
            print(f"  id={log.id}")
            print(f"  channel={log.channel}")
            print(f"  event={log.event}")
            print(f"  status={log.status}")
            print(f"  recipient={log.recipient}")
            print(f"  subject={log.subject}")
            print(f"  sent_at={log.sent_at}")
            print(f"  metadata_json={log.metadata_json}")
            print()

            check("log channel console", log.channel == "console")
            check("log event reminder_due", log.event == "reminder_due")
            check("log status sent", log.status == "sent")
            check("log recipient non vuoto", bool(log.recipient))
            check("log subject non vuoto", bool(log.subject))
            check("log sent_at popolato", log.sent_at is not None)

        # 3. Secondo run: non deve duplicare
        summary_second = send_due_reminders(
            db,
            now=now,
            dry_run=False,
            limit=10,
            channel_override="console",
            only_reminder_ids=[past_id, future_id, completed_id],
        )

        check("secondo run candidati = 0", summary_second["candidates"] == 0, f"summary={summary_second}")
        check("secondo run sent = 0", summary_second["sent"] == 0, f"summary={summary_second}")

        db.expire_all()

        past_logs_second = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.reminder_id == UUID(past_id),
                NotificationLog.event == "reminder_due",
                NotificationLog.status == "sent",
            )
            .count()
        )

        check("nessun log sent duplicato", past_logs_second == 1, f"count={past_logs_second}")

    finally:
        try:
            cleanup_ids = [x for x in [past_id, future_id, completed_id] if x]

            if cleanup_ids:
                db.query(NotificationLog).filter(
                    NotificationLog.reminder_id.in_([UUID(x) for x in cleanup_ids])
                ).delete(synchronize_session=False)

                db.query(Reminder).filter(
                    Reminder.id.in_([UUID(x) for x in cleanup_ids])
                ).delete(synchronize_session=False)

                db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup finale fallito: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

        db.close()

except Exception as exc:  # noqa: BLE001
    print(f"ERRORE: {exc}")
    failures.append(str(exc))

print()

if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test di notifiche promemoria Step 4A sono passati.")