"""
Sprint B Step 4F.

Test deterministico per il wiring delle preferenze utente nel batch.

Run sequenziali sullo stesso utente:
- run 0: dry-run con notifiche disabilitate -> skipped, nessun log;
- run 1: execute con notifiche disabilitate -> skipped, nessun log;
- run 2: execute con canale console -> sent (log sent/console);
- run 3: execute con canale smtp senza host -> failed (log failed/smtp);
- run 4: execute con canale console sul reminder saltato -> sent
         (lo skip non "consuma" il promemoria).
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
from app.db.settings_models import UserSettings
from app.db.therapy_models import Reminder
from app.services.family import ensure_family_and_self_patient
from app.services.reminder_notifications import send_due_reminders

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
TITLE_PREFIX = "TEST B step4F wiring "
NOTES_MARKER = "b-step4f-wiring-test"

failures: list[str] = []

user = None
patient = None
r1_id: str | None = None
r2_id: str | None = None
r3_id: str | None = None

settings_backup: dict | None = None
settings_existed = False


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


def count_logs(db, reminder_id: str, status: str | None = None) -> int:
    q = db.query(NotificationLog).filter(
        NotificationLog.reminder_id == UUID(reminder_id)
    )
    if status:
        q = q.filter(NotificationLog.status == status)
    return q.count()


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

    previous_ids = [r.id for r in previous]

    if previous_ids:
        db.query(NotificationLog).filter(
            NotificationLog.reminder_id.in_(previous_ids)
        ).delete(synchronize_session=False)

        for reminder in previous:
            db.delete(reminder)

        db.commit()


def make_reminder(db, user, patient, suffix: str, now: datetime) -> Reminder:
    reminder = Reminder(
        patient_id=patient.id,
        therapy_id=None,
        title=f"{TITLE_PREFIX}{suffix} {RUN_ID}",
        reminder_type="medication",
        scheduled_at=now - timedelta(hours=1),
        status="pending",
        notes=NOTES_MARKER,
        created_by_user_id=user.id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def set_settings(db, user, enabled=None, channel=None, smtp_host="__unset__"):
    settings = db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    if enabled is not None:
        settings.notifications_enabled = enabled
    if channel is not None:
        settings.notification_channel = channel
    if smtp_host != "__unset__":
        settings.smtp_host = smtp_host

    db.commit()
    db.refresh(settings)
    return settings


try:
    db = SessionLocal()

    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            raise RuntimeError("Nessun utente nel DB.")

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        # Backup impostazioni esistenti per restore finale
        existing = db.get(UserSettings, user.id)
        settings_existed = existing is not None
        if existing is not None:
            settings_backup = {
                "notification_channel": existing.notification_channel,
                "notifications_enabled": existing.notifications_enabled,
                "smtp_host": existing.smtp_host,
                "smtp_port": existing.smtp_port,
                "smtp_user": existing.smtp_user,
                "smtp_password": existing.smtp_password,
                "smtp_from": existing.smtp_from,
                "smtp_use_tls": existing.smtp_use_tls,
            }

        cleanup_previous(db)

        now = datetime.now(timezone.utc)

        r1 = make_reminder(db, user, patient, "r1", now)
        r2 = make_reminder(db, user, patient, "r2", now)
        r3 = make_reminder(db, user, patient, "r3", now)

        r1_id, r2_id, r3_id = str(r1.id), str(r2.id), str(r3.id)

        print("Setup creato:")
        print(f"  r1_id={r1_id}")
        print(f"  r2_id={r2_id}")
        print(f"  r3_id={r3_id}")
        print()

        # ---- run 0: dry-run con notifiche disabilitate ----
        set_settings(db, user, enabled=False, channel="console")

        s0 = send_due_reminders(db, now=now, dry_run=True, limit=10, only_reminder_ids=[r1_id])
        check("run0 dry-run candidati=1", s0["candidates"] == 1, f"{s0}")
        check("run0 dry-run skipped=1", s0["skipped"] == 1, f"{s0}")
        check("run0 nessun log r1", count_logs(db, r1_id) == 0)

        # ---- run 1: execute con notifiche disabilitate ----
        s1 = send_due_reminders(db, now=now, dry_run=False, limit=10, only_reminder_ids=[r1_id])
        check("run1 skipped=1", s1["skipped"] == 1, f"{s1}")
        check("run1 sent=0", s1["sent"] == 0, f"{s1}")
        check("run1 nessun log r1", count_logs(db, r1_id) == 0)

        # ---- run 2: execute con canale console ----
        set_settings(db, user, enabled=True, channel="console")

        s2 = send_due_reminders(db, now=now, dry_run=False, limit=10, only_reminder_ids=[r2_id])
        check("run2 sent=1", s2["sent"] == 1, f"{s2}")
        check("run2 log sent r2", count_logs(db, r2_id, "sent") == 1)
        check("run2 log channel console",
              db.query(NotificationLog).filter(
                  NotificationLog.reminder_id == UUID(r2_id),
                  NotificationLog.channel == "console",
              ).count() == 1)

        # ---- run 3: execute con canale smtp senza host ----
        set_settings(db, user, channel="smtp", smtp_host=None)

        s3 = send_due_reminders(db, now=now, dry_run=False, limit=10, only_reminder_ids=[r3_id])
        check("run3 failed=1", s3["failed"] == 1, f"{s3}")
        check("run3 log failed r3", count_logs(db, r3_id, "failed") == 1)
        check("run3 log channel smtp",
              db.query(NotificationLog).filter(
                  NotificationLog.reminder_id == UUID(r3_id),
                  NotificationLog.channel == "smtp",
              ).count() == 1)

        failed_log = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.reminder_id == UUID(r3_id),
                NotificationLog.status == "failed",
            )
            .first()
        )
        check("run3 log error popolato", failed_log is not None and bool(failed_log.error))

        # ---- run 4: r1 (saltato prima) ora con console -> sent ----
        set_settings(db, user, channel="console")

        s4 = send_due_reminders(db, now=now, dry_run=False, limit=10, only_reminder_ids=[r1_id])
        check("run4 sent=1 (skip non consuma)", s4["sent"] == 1, f"{s4}")
        check("run4 log sent r1", count_logs(db, r1_id, "sent") == 1)

    finally:
        # Cleanup reminder + log
        try:
            ids = [x for x in [r1_id, r2_id, r3_id] if x]
            if ids:
                uuids = [UUID(x) for x in ids]
                db.query(NotificationLog).filter(
                    NotificationLog.reminder_id.in_(uuids)
                ).delete(synchronize_session=False)
                db.query(Reminder).filter(Reminder.id.in_(uuids)).delete(
                    synchronize_session=False
                )
                db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup reminder fallito: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

        # Restore impostazioni utente
        try:
            current = db.get(UserSettings, user.id) if user is not None else None
            if not settings_existed:
                if current is not None:
                    db.delete(current)
                    db.commit()
            elif settings_backup is not None:
                if current is None:
                    current = UserSettings(user_id=user.id) if user is not None else None
                    db.add(current)
                for key, value in settings_backup.items():
                    setattr(current, key, value)
                db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN restore settings fallito: {exc}")
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

print("Tutti i test di wiring preferenze Step 4F sono passati.")