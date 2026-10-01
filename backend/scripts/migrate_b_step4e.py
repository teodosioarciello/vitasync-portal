"""
Sprint B Step 4E: migrazione tabella user_settings.

Crea la tabella user_settings con relazione 1:1 verso users.
Idempotente: non fallisce se la tabella esiste gia'.
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
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        notification_channel VARCHAR(32) NOT NULL DEFAULT 'console',
        notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        smtp_host VARCHAR(255) NULL,
        smtp_port INTEGER NULL,
        smtp_user VARCHAR(255) NULL,
        smtp_password VARCHAR(255) NULL,
        smtp_from VARCHAR(255) NULL,
        smtp_use_tls BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_user_settings_channel CHECK (notification_channel IN ('console', 'smtp'))
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_settings_user_id ON user_settings (user_id)",
]


def main() -> None:
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
            first_line = stmt.strip().splitlines()[0]
            print(f"OK: {first_line}")

    print("Migrazione B step 4E completata.")


if __name__ == "__main__":
    main()