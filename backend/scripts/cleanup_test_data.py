"""
Micro-step igiene fixture/test data.

Script prudente per individuare ed eventualmente eliminare dati di test
lasciati dagli sprint precedenti.

Default: DRY-RUN, non elimina nulla.
Per eliminare davvero serve --execute.

Di default NON elimina i seed/demo fixtures canonici, ad esempio:
- lab-report-synthetic.pdf
- ocr-lab-report-synthetic.png
- ocr-synonyms-synthetic.pdf
- promemoria fixture
- terapia sintetica di test

Per includere anche quelli, usare esplicitamente:
    --include-seed-fixtures

NON elimina audit log.
NON elimina utenti/pazienti.
NON tocca dati che non corrispondono ai pattern di test.

Esempi:
    docker compose exec backend python scripts/cleanup_test_data.py
    docker compose exec backend python scripts/cleanup_test_data.py --execute
    docker compose exec backend python scripts/cleanup_test_data.py --include-seed-fixtures --dry-run
    docker compose exec backend python scripts/cleanup_test_data.py --include-seed-fixtures --execute
"""

import argparse
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import or_

from app.core.config import settings
from app.db.models import Document, LabTest
from app.db.session import SessionLocal
from app.db.therapy_models import Medicine, Reminder, Therapy
from app.services.document_delete import delete_document_and_file

logger = logging.getLogger(__name__)

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

# =========================================================================
# PATTERN TRANSITORI DI TEST
# Questi vengono considerati sempre candidati.
# =========================================================================

TRANSIENT_DOC_TITLE_PATTERNS = (
    "TEST C-media%",
    "TEST retention%",
    "TEST trend%",
    "CLEANUP TEST%",
)

TRANSIENT_DOC_STORAGE_KEY_PATTERNS = (
    "_fixtures/test-%",
    "_fixtures/audit-user-test.pdf",
    "_fixtures/trend-trash-%",
    "_fixtures/retention-purge-%",
    "_fixtures/retention-report-%",
    "_fixtures/cleanup-test-%",
)

TRANSIENT_DOC_SOURCE_FILENAME_PATTERNS = (
    "audit-user-test.pdf",
    "test-delete-document.pdf",
    "test-soft-delete-document.pdf",
    "trend-trash-%",
    "retention-purge-%",
    "retention-report-%",
    "cleanup-test-%",
)

TRANSIENT_FILE_GLOB_PATTERNS = (
    "audit-user-test.pdf",
    "test-*.pdf",
    "test-*.png",
    "trend-trash-*.pdf",
    "retention-purge-*.pdf",
    "retention-report-*.pdf",
    "cleanup-test-*",
)

TRANSIENT_MEDICINE_NAME_PATTERNS = (
    "TEST C-media%",
    "CLEANUP TEST%",
)

TRANSIENT_MEDICINE_NOTES_PATTERNS = (
    "audit identity step5%",
    "c-media-soft-delete-test",
    "cleanup-test%",
)

TRANSIENT_THERAPY_NOTES_PATTERNS = (
    "audit identity step5%",
    "c-media-soft-delete-test",
    "cleanup-test%",
)

TRANSIENT_THERAPY_INSTRUCTIONS_PATTERNS = (
    "Test audit identity step5%",
    "Test soft delete flow.%",
    "Cleanup test therapy%",
)

TRANSIENT_THERAPY_PRESCRIBED_BY_PATTERNS = (
    "Cleanup test",
)

TRANSIENT_REMINDER_TITLE_PATTERNS = (
    "TEST C-media%",
    "CLEANUP TEST%",
)

TRANSIENT_REMINDER_NOTES_PATTERNS = (
    "audit identity step5%",
    "c-media-soft-delete-test",
    "cleanup-test%",
)

TRANSIENT_LABTEST_CODE_PATTERNS = (
    "test_soft_delete%",
    "trend_trash_%",
    "retention_purge_%",
    "retention_report_%",
    "cleanup_test_%",
)

TRANSIENT_LABTEST_NAME_PATTERNS = (
    "TEST SOFT DELETE%",
    "TREND TRASH PROOF%",
    "RETENTION PURGE%",
    "RETENTION REPORT%",
    "CLEANUP TEST%",
)

# =========================================================================
# PATTERN SEED/DEMO FIXTURES
# Questi vengono considerati candidati SOLO con --include-seed-fixtures.
# =========================================================================

SEED_DOC_TITLE_PATTERNS = (
    "Fixture%",
)

SEED_DOC_STORAGE_KEY_PATTERNS = (
    "_fixtures/lab-report-synthetic.pdf",
    "_fixtures/ocr-lab-report-synthetic.png",
    "_fixtures/ocr-synonyms-synthetic.pdf",
)

SEED_DOC_SOURCE_FILENAME_PATTERNS = (
    "lab-report-synthetic.pdf",
    "ocr-lab-report-synthetic.png",
    "ocr-synonyms-synthetic.pdf",
)

SEED_FILE_GLOB_PATTERNS = (
    "lab-report-synthetic.pdf",
    "ocr-lab-report-synthetic.png",
    "ocr-synonyms-synthetic.pdf",
)

SEED_THERAPY_NOTES_PATTERNS = (
    "Terapia sintetica di test.",
)

SEED_THERAPY_INSTRUCTIONS_PATTERNS = (
    "Assumere dopo i pasti se dolore o febbre.",
)

SEED_THERAPY_PRESCRIBED_BY_PATTERNS = (
    "Medico fixture",
)

SEED_REMINDER_TITLE_PATTERNS = (
    "Promemoria fixture%",
)

SEED_REMINDER_NOTES_PATTERNS = (
    "Esempio di promemoria%",
)


def _like_any(column, patterns):
    if not patterns:
        return None
    return or_(*[column.like(pattern) for pattern in patterns])


def _conditions(*items):
    return [item for item in items if item is not None]


def _find_orphan_fixture_files(include_seed_fixtures: bool) -> list[Path]:
    root = LOCAL_STORAGE_ROOT.resolve()
    fixtures = (root / "_fixtures").resolve()

    if not fixtures.exists():
        return []

    patterns = list(TRANSIENT_FILE_GLOB_PATTERNS)

    if include_seed_fixtures:
        patterns.extend(SEED_FILE_GLOB_PATTERNS)

    found: list[Path] = []

    for pattern in patterns:
        for path in fixtures.glob(pattern):
            try:
                resolved = path.resolve()
            except Exception:
                continue

            if resolved.is_file() and resolved.is_relative_to(fixtures):
                found.append(resolved)

    return sorted(set(found), key=str)


def find_candidates(db, include_seed_fixtures: bool = False):
    doc_conditions = _conditions(
        _like_any(Document.title, TRANSIENT_DOC_TITLE_PATTERNS),
        _like_any(Document.storage_key, TRANSIENT_DOC_STORAGE_KEY_PATTERNS),
        _like_any(Document.source_filename, TRANSIENT_DOC_SOURCE_FILENAME_PATTERNS),
    )

    if include_seed_fixtures:
        doc_conditions.extend(
            _conditions(
                _like_any(Document.title, SEED_DOC_TITLE_PATTERNS),
                _like_any(Document.storage_key, SEED_DOC_STORAGE_KEY_PATTERNS),
                _like_any(Document.source_filename, SEED_DOC_SOURCE_FILENAME_PATTERNS),
            )
        )

    docs = (
        db.query(Document)
        .filter(or_(*doc_conditions))
        .order_by(Document.created_at.asc())
        .all()
    )

    doc_ids = [doc.id for doc in docs]

    med_conditions = _conditions(
        _like_any(Medicine.name, TRANSIENT_MEDICINE_NAME_PATTERNS),
        _like_any(Medicine.notes, TRANSIENT_MEDICINE_NOTES_PATTERNS),
    )

    meds = (
        db.query(Medicine)
        .filter(or_(*med_conditions))
        .order_by(Medicine.created_at.asc())
        .all()
    )

    med_ids = [med.id for med in meds]

    therapy_conditions = _conditions(
        _like_any(Therapy.notes, TRANSIENT_THERAPY_NOTES_PATTERNS),
        _like_any(Therapy.instructions, TRANSIENT_THERAPY_INSTRUCTIONS_PATTERNS),
        _like_any(Therapy.prescribed_by, TRANSIENT_THERAPY_PRESCRIBED_BY_PATTERNS),
    )

    if include_seed_fixtures:
        therapy_conditions.extend(
            _conditions(
                _like_any(Therapy.notes, SEED_THERAPY_NOTES_PATTERNS),
                _like_any(Therapy.instructions, SEED_THERAPY_INSTRUCTIONS_PATTERNS),
                _like_any(Therapy.prescribed_by, SEED_THERAPY_PRESCRIBED_BY_PATTERNS),
            )
        )

    if med_ids:
        therapy_conditions.append(Therapy.medicine_id.in_(med_ids))

    if doc_ids:
        therapy_conditions.append(Therapy.prescription_document_id.in_(doc_ids))

    therapies = (
        db.query(Therapy)
        .filter(or_(*therapy_conditions))
        .order_by(Therapy.created_at.asc())
        .all()
    )

    therapy_ids = [therapy.id for therapy in therapies]

    reminder_conditions = _conditions(
        _like_any(Reminder.title, TRANSIENT_REMINDER_TITLE_PATTERNS),
        _like_any(Reminder.notes, TRANSIENT_REMINDER_NOTES_PATTERNS),
    )

    if include_seed_fixtures:
        reminder_conditions.extend(
            _conditions(
                _like_any(Reminder.title, SEED_REMINDER_TITLE_PATTERNS),
                _like_any(Reminder.notes, SEED_REMINDER_NOTES_PATTERNS),
            )
        )

    if therapy_ids:
        reminder_conditions.append(Reminder.therapy_id.in_(therapy_ids))

    reminders = (
        db.query(Reminder)
        .filter(or_(*reminder_conditions))
        .order_by(Reminder.created_at.asc())
        .all()
    )

    lab_conditions = _conditions(
        _like_any(LabTest.test_code, TRANSIENT_LABTEST_CODE_PATTERNS),
        _like_any(LabTest.test_name_original, TRANSIENT_LABTEST_NAME_PATTERNS),
        _like_any(LabTest.test_name_normalized, TRANSIENT_LABTEST_NAME_PATTERNS),
    )

    if doc_ids:
        lab_conditions.append(LabTest.document_id.in_(doc_ids))

    labs = (
        db.query(LabTest)
        .filter(or_(*lab_conditions))
        .order_by(LabTest.created_at.asc())
        .all()
    )

    files = _find_orphan_fixture_files(include_seed_fixtures=include_seed_fixtures)

    return {
        "documents": docs,
        "medicines": meds,
        "therapies": therapies,
        "reminders": reminders,
        "lab_tests": labs,
        "files": files,
    }


def print_summary(candidates: dict, include_seed_fixtures: bool) -> None:
    print("Seed/demo fixtures inclusi:", "SI" if include_seed_fixtures else "NO")
    print()
    print("Candidati trovati:")

    for label, rows in (
        ("documents", candidates["documents"]),
        ("medicines", candidates["medicines"]),
        ("therapies", candidates["therapies"]),
        ("reminders", candidates["reminders"]),
        ("lab_tests", candidates["lab_tests"]),
    ):
        print(f"  {label}: {len(rows)}")

    print(f"  orphan_fixture_files: {len(candidates['files'])}")
    print()

    for label, rows in (
        ("documents", candidates["documents"]),
        ("medicines", candidates["medicines"]),
        ("therapies", candidates["therapies"]),
        ("reminders", candidates["reminders"]),
        ("lab_tests", candidates["lab_tests"]),
    ):
        if not rows:
            continue

        print(f"  {label} dettagli (max 20):")

        for row in rows[:20]:
            if label == "documents":
                print(
                    f"    - id={row.id} | title={row.title!r} | "
                    f"storage_key={row.storage_key!r} | deleted_at={row.deleted_at}"
                )
            elif label == "medicines":
                print(
                    f"    - id={row.id} | name={row.name!r} | notes={row.notes!r}"
                )
            elif label == "therapies":
                print(
                    f"    - id={row.id} | notes={row.notes!r} | "
                    f"instructions={row.instructions!r}"
                )
            elif label == "reminders":
                print(
                    f"    - id={row.id} | title={row.title!r} | notes={row.notes!r}"
                )
            elif label == "lab_tests":
                print(
                    f"    - id={row.id} | code={row.test_code!r} | "
                    f"name={row.test_name_original!r}"
                )

        print()

    if candidates["files"]:
        print("  orphan_fixture_files dettagli (max 50):")
        for path in candidates["files"][:50]:
            print(f"    - {path}")
        print()


def execute_cleanup(db, candidates: dict, execute: bool = False):
    stats = {
        "candidates_documents": len(candidates["documents"]),
        "candidates_medicines": len(candidates["medicines"]),
        "candidates_therapies": len(candidates["therapies"]),
        "candidates_reminders": len(candidates["reminders"]),
        "candidates_lab_tests": len(candidates["lab_tests"]),
        "candidates_orphan_files": len(candidates["files"]),
        "deleted_reminders": 0,
        "deleted_therapies": 0,
        "deleted_medicines": 0,
        "deleted_lab_tests": 0,
        "deleted_documents": 0,
        "deleted_document_files": 0,
        "deleted_orphan_files": 0,
    }

    failed: list[tuple[str, str]] = []

    if not execute:
        return stats, failed

    deletion_plan = (
        ("reminders", Reminder, [row.id for row in candidates["reminders"]]),
        ("therapies", Therapy, [row.id for row in candidates["therapies"]]),
        ("medicines", Medicine, [row.id for row in candidates["medicines"]]),
        ("lab_tests", LabTest, [row.id for row in candidates["lab_tests"]]),
    )

    for label, model, ids in deletion_plan:
        if not ids:
            continue

        try:
            count = (
                db.query(model)
                .filter(model.id.in_(ids))
                .delete(synchronize_session=False)
            )
            db.commit()
            stats[f"deleted_{label}"] = count
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append((label, str(exc)))
            logger.exception("Cleanup %s fallito", label)

    for doc in candidates["documents"]:
        try:
            file_existed = delete_document_and_file(db, doc)
            stats["deleted_documents"] += 1
            if file_existed:
                stats["deleted_document_files"] += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append((str(doc.id), str(exc)))
            logger.exception("Cleanup documento %s fallito", doc.id)

    for path in candidates["files"]:
        try:
            if path.exists():
                path.unlink()
                stats["deleted_orphan_files"] += 1
        except Exception as exc:  # noqa: BLE001
            failed.append((str(path), str(exc)))
            logger.exception("Cleanup file orfano %s fallito", path)

    return stats, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Individua ed eventualmente elimina dati di test/fixture in modo prudente."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Esegue realmente le eliminazioni. Senza questa opzione fa solo dry-run.",
    )
    parser.add_argument(
        "--include-seed-fixtures",
        action="store_true",
        help=(
            "Include anche i seed/demo fixtures canonici, ad esempio "
            "lab-report-synthetic, ocr-lab-report-synthetic, ocr-synonyms-synthetic, "
            "promemoria fixture e terapia sintetica di test."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Esegue esplicitamente solo il dry-run. E' il comportamento di default; "
            "serve per coerenza con la documentazione. Se passato insieme a --execute, "
            "--dry-run ha la precedenza per sicurezza."
        ),
    )

    args = parser.parse_args()

    if args.execute and args.dry_run:
        print("ATTENZIONE: passati sia --execute sia --dry-run. Per sicurezza eseguo DRY-RUN.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    mode = "DRY-RUN" if args.dry_run or not args.execute else "EXECUTE"

    print(f"Modalita': {mode}")
    print("Nota: gli audit log NON vengono eliminati.")
    print()

    db = SessionLocal()

    try:
        candidates = find_candidates(
            db,
            include_seed_fixtures=args.include_seed_fixtures,
        )

        print_summary(candidates, include_seed_fixtures=args.include_seed_fixtures)

        if not args.execute:
            print("DRY-RUN completato. Nessun dato eliminato.")
            print("Per eliminare davvero, riesegui con --execute.")
            if not args.include_seed_fixtures:
                print("Per includere anche i seed/demo fixtures, usa --include-seed-fixtures.")
            return 0

        stats, failed = execute_cleanup(db, candidates, execute=True)

        print("Esito cleanup:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        if failed:
            print()
            print("Fallimenti:")
            for label, err in failed:
                print(f"  - {label}: {err}")
            return 1

        print()
        print("Cleanup completato.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())