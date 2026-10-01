"""
Migrazione Sprint B Step 4A.

Crea la tabella notification_logs e indici correlati, in modo idempotente.

Da eseguire dentro il container backend:
    docker compose run --rm backend python scripts/migrate_b_step4a.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text

from app.db.session import engine

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS notification_logs (
        id UUID PRIMARY KEY,
        reminder_id UUID NULL REFERENCES reminders(id) ON DELETE SET NULL,
        patient_id UUID NULL REFERENCES patients(id) ON DELETE SET NULL,
        user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
        channel VARCHAR(32) NOT NULL,
        event VARCHAR(64) NOT NULL DEFAULT 'reminder_due',
        status VARCHAR(32) NOT NULL,
        recipient VARCHAR(255) NULL,
        subject VARCHAR(255) NULL,
        error TEXT NULL,
        scheduled_for TIMESTAMPTZ NOT NULL,
        sent_at TIMESTAMPTZ NULL,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_notification_log_channel CHECK (channel IN ('console', 'smtp')),
        CONSTRAINT ck_notification_log_event CHECK (event IN ('reminder_due')),
        CONSTRAINT ck_notification_log_status CHECK (status IN ('sent', 'failed', 'skipped'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_notification_logs_reminder_id ON notification_logs (reminder_id)",
    "CREATE INDEX IF NOT EXISTS ix_notification_logs_patient_id ON notification_logs (patient_id)",
    "CREATE INDEX IF NOT EXISTS ix_notification_logs_user_id ON notification_logs (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_notification_logs_status ON notification_logs (status)",
    "CREATE INDEX IF NOT EXISTS ix_notification_logs_created_at ON notification_logs (created_at)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_logs_successful_reminder_event
    ON notification_logs (reminder_id, event)
    WHERE status = 'sent' AND reminder_id IS NOT NULL
    """,
]


def main() -> None:
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
            first_line = stmt.strip().splitlines()[0]
            print(f"OK: {first_line}")

    print("Migrazione B step 4A completata.")


if __name__ == "__main__":
    main()