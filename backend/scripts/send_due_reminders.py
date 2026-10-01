"""
Sprint B Step 4A.

Script manuale per notificare promemoria scaduti.

Esempi:
    docker compose exec backend python scripts/send_due_reminders.py --dry-run
    docker compose exec backend python scripts/send_due_reminders.py
    docker compose exec backend python scripts/send_due_reminders.py --limit 50

Default:
- NOTIFICATION_CHANNEL=console
- NOTIFICATIONS_ENABLED=true

Per SMTP reale:
    NOTIFICATION_CHANNEL=smtp
    NOTIFICATIONS_ENABLED=true
    SMTP_HOST=...
    SMTP_PORT=587
    SMTP_USER=...
    SMTP_PASSWORD=...
    SMTP_FROM=...
"""

import argparse
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.services.reminder_notifications import (
    CHANNEL_SMTP,
    get_channel,
    notifications_enabled,
    send_due_reminders,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Notifica promemoria scaduti in modo manuale e supervisionato."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra solo i candidati, senza inviare e senza registrare log.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Numero massimo di promemoria da processare. Default: 100.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    channel = get_channel()
    enabled = notifications_enabled()

    print(f"Canale notifiche: {channel}")
    print(f"Notificazioni abilitate: {enabled}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Limit: {args.limit}")
    print()

    if channel == CHANNEL_SMTP and not enabled:
        print("SMTP selezionato ma NOTIFICATIONS_ENABLED non e' true. Nessuna azione.")
        return 0

    db = SessionLocal()

    try:
        summary = send_due_reminders(
            db,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        print()
        print("Esito:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

        if summary["failed"] > 0:
            return 1

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())