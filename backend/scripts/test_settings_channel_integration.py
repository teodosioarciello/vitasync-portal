"""
Sprint B Step 4E - test di integrazione.

Verifica che le impostazioni utente guidino il pipeline di invio:
- canale smtp senza host configurato => notifica failed (non inviata);
- notifiche disabilitate dall'utente => notifica skipped;
- cleanup completo a fine test.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import User
from app.db.notification_models import NotificationLog
from app.db.session import SessionLocal
from app.db.settings_models import UserSettings
from app.db.therapy_models import Reminder
from app.services.family import ensure_family_and_self_patient
from app.services.reminder_notifications import send_due_reminders

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
TITLE = f"TEST 4E integration {RUN_ID}"

failures: list[str] = []

db = None
user = None
reminder_id = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


try:
    db = SessionLocal()

    user = db.query(User).order_by(User.created_at.asc()).first()
    if not user:
        raise RuntimeError("Nessun utente nel DB.")

    _, patient = ensure_family_and_self_patient(db, user)

    reminder = Reminder(
        patient_id=patient.id,
        therapy_id=None,
        title=TITLE,
        reminder_type="medication",
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status="pending",
        notes="4e-integration-test",
        created_by_user_id=user.id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    reminder_id = reminder.id

    settings = db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    settings.notification_channel = "smtp"
    settings.notifications_enabled = True
    settings.smtp_host = None
    db.commit()

    print(f"reminder_id={reminder_id}")
    print()

    # 1. smtp senza host => failed
    summary = send_due_reminders(
        db,
        only_reminder_ids=[str(reminder_id)],
        channel_override=None,
    )

    check("smtp senza host => failed=1", summary["failed"] == 1, str(summary))
    check("smtp senza host => sent=0", summary["sent"] == 0, str(summary))

    db.expire_all()
    failed_log = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.reminder_id == reminder_id,
            NotificationLog.status == "failed",
        )
        .order_by(NotificationLog.created_at.desc())
        .first()
    )

    check("log failed presente", failed_log is not None)
    check("log failed channel smtp", failed_log is not None and failed_log.channel == "smtp")

    # 2. notifiche disabilitate => skipped
    settings.notifications_enabled = False
    db.commit()

    summary2 = send_due_reminders(
        db,
        only_reminder_ids=[str(reminder_id)],
        channel_override=None,
    )

    check("notifiche disabilitate => skipped=1", summary2["skipped"] == 1, str(summary2))
    check("notifiche disabilitate => sent=0", summary2["sent"] == 0, str(summary2))

    # Nota: lo skip per "notifiche disabilitate" non genera un NotificationLog
    # (non c'è stato alcun tentativo di invio), ma il summary riporta skipped=1.

finally:
    if db is not None:
        try:
            if reminder_id is not None:
                db.query(NotificationLog).filter(
                    NotificationLog.reminder_id == reminder_id
                ).delete(synchronize_session=False)

                rem = db.get(Reminder, reminder_id)
                if rem is not None:
                    db.delete(rem)

            if user is not None:
                st = db.get(UserSettings, user.id)
                if st is not None:
                    db.delete(st)

            db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup fallito: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

        db.close()

print()

if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test di integrazione canale Step 4E sono passati.")