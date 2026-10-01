"""
Sprint C-media Step 8.

Report retention sicuro del cestino documenti.

Questo script NON elimina nulla.
Elenca soltanto i documenti che sarebbero candidabili alla purge definitiva
secondo la retention configurata.

Default retention: 30 giorni, configurabile con:
- env var TRASH_RETENTION_DAYS;
- oppure --days.

Esempio:
    docker compose exec backend python scripts/report_retention_trash.py --days 30
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.audit import record_audit

DEFAULT_RETENTION_DAYS = int(os.getenv("TRASH_RETENTION_DAYS", "30"))
MAX_IDS_IN_AUDIT = 100


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def collect_candidates(
    db,
    days: int,
    only_document_ids: list[str] | None = None,
) -> list[dict]:
    """
    Ritorna i documenti nel cestino piu' vecchi della soglia di retention.

    Se only_document_ids e' fornito, considera solo quei documenti.
    Questo serve ai test per non includere dati preesistenti.
    """
    if days <= 0:
        raise ValueError("days deve essere maggiore di 0.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.query(Document).filter(
        Document.deleted_at.isnot(None),
        Document.deleted_at <= cutoff,
    )

    if only_document_ids is not None:
        if not only_document_ids:
            return []

        uuid_ids = [UUID(str(x)) for x in only_document_ids]
        query = query.filter(Document.id.in_(uuid_ids))

    rows = query.order_by(Document.deleted_at.asc()).all()

    return [
        {
            "id": str(row.id),
            "patient_id": str(row.patient_id),
            "uploaded_by_user_id": str(row.uploaded_by_user_id),
            "title": row.title,
            "deleted_at": _iso(row.deleted_at),
        }
        for row in rows
    ]


def build_extra(days: int, candidates: list[dict]) -> str:
    ids = [c["id"] for c in candidates]
    included = ids[:MAX_IDS_IN_AUDIT]
    truncated = len(ids) > len(included)
    oldest = candidates[0]["deleted_at"] if candidates else None

    return (
        f"days={days};"
        f"candidates={len(candidates)};"
        f"oldest_deleted_at={oldest or ''};"
        f"candidate_document_ids={','.join(included)};"
        f"truncated={'true' if truncated else 'false'}"
    )


def report_retention(
    db,
    days: int,
    only_document_ids: list[str] | None = None,
    write_audit: bool = True,
) -> list[dict]:
    candidates = collect_candidates(
        db,
        days=days,
        only_document_ids=only_document_ids,
    )

    if write_audit:
        record_audit(
            action="document.retention_report",
            method="SYSTEM",
            path="scripts/report_retention_trash.py",
            status_code=None,
            ip_address=None,
            user_agent=None,
            user_id=None,
            extra=build_extra(days, candidates),
        )

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un report retention sicuro senza eliminare documenti."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=(
            "Giorni di retention. Default: valore env TRASH_RETENTION_DAYS, "
            "oppure 30 se non impostato."
        ),
    )

    args = parser.parse_args()
    days = args.days if args.days is not None else DEFAULT_RETENTION_DAYS

    print(f"Retention giorni: {days}")
    print("Modalita': REPORT. Nessun documento verra' eliminato.")
    print()

    db = SessionLocal()

    try:
        candidates = report_retention(db, days=days)

        print(f"Candidati: {len(candidates)}")

        for candidate in candidates:
            print(
                f"- {candidate['id']} | "
                f"deleted_at={candidate['deleted_at']} | "
                f"{candidate['title']}"
            )

        print()
        print("Report retention completato. Nessun documento eliminato.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())