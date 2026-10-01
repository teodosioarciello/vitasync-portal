"""
Sprint C-media Step 7.

Script manuale di retention/purge del cestino documenti.

Elimina definitivamente solo i documenti con:
- deleted_at non nullo;
- deleted_at piu' vecchio della soglia di retention.

Default retention: 30 giorni, configurabile con:
- env var TRASH_RETENTION_DAYS;
- oppure --days.

Esempi:
    docker compose exec backend python scripts/purge_expired_trash.py --days 30 --dry-run
    docker compose exec backend python scripts/purge_expired_trash.py --days 30
"""

import argparse
import logging
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
from app.services.document_delete import delete_document_and_file

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = int(os.getenv("TRASH_RETENTION_DAYS", "30"))


def purge_expired(
    db,
    days: int,
    dry_run: bool = False,
    only_document_ids: list[str] | None = None,
) -> tuple[list[str], list[tuple[str, str]], int]:
    """
    Elimina definitivamente i documenti nel cestino piu' vecchi di `days` giorni.

    Ritorna:
      (purged_ids, failed, candidates_count)

    Se `only_document_ids` e' fornito, considera solo quei documenti.
    Questo serve ai test per non toccare dati reali/preesistenti.
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
            return [], [], 0

        uuid_ids = [UUID(str(x)) for x in only_document_ids]
        query = query.filter(Document.id.in_(uuid_ids))

    rows = query.order_by(Document.deleted_at.asc()).all()

    purged: list[str] = []
    failed: list[tuple[str, str]] = []

    for doc in rows:
        doc_id = str(doc.id)
        patient_id = str(doc.patient_id)
        uploaded_by_user_id = str(doc.uploaded_by_user_id)
        deleted_at = doc.deleted_at.isoformat() if doc.deleted_at else None

        if dry_run:
            print(f"DRY-RUN: documento {doc_id} eliminabile (deleted_at={deleted_at})")
            purged.append(doc_id)
            continue

        try:
            file_existed = delete_document_and_file(db, doc)

            record_audit(
                action="document.retention_purge",
                method="SYSTEM",
                path="scripts/purge_expired_trash.py",
                status_code=None,
                ip_address=None,
                user_agent=None,
                user_id=None,
                extra=(
                    f"document_id={doc_id};"
                    f"patient_id={patient_id};"
                    f"uploaded_by_user_id={uploaded_by_user_id};"
                    f"deleted_at={deleted_at};"
                    f"file_existed={file_existed}"
                ),
            )

            print(f"OK: documento {doc_id} purgato definitivamente.")
            purged.append(doc_id)

        except Exception as exc:  # noqa: BLE001
            logger.exception("Purge fallita per documento %s", doc_id)

            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

            failed.append((doc_id, str(exc)))

    return purged, failed, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purga definitivamente i documenti nel cestino oltre la retention."
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra cosa verrebbe eliminato senza eliminare nulla.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    days = args.days if args.days is not None else DEFAULT_RETENTION_DAYS

    print(f"Retention giorni: {days}")
    print(f"Dry-run: {args.dry_run}")
    print()

    db = SessionLocal()

    try:
        purged, failed, candidates = purge_expired(
            db,
            days=days,
            dry_run=args.dry_run,
        )

        print()
        print(f"Candidati: {candidates}")
        print(f"Purgati: {len(purged)}")
        print(f"Falliti: {len(failed)}")

        for doc_id, err in failed:
            print(f"FAIL {doc_id}: {err}")

        if failed:
            return 1

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())