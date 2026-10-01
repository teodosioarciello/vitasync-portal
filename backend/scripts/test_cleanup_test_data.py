"""
Micro-step igiene fixture/test data.

Test deterministico per cleanup_test_data.py.

Crea:
- entita' di test corrispondenti ai pattern;
- entita' di controllo NON corrispondenti ai pattern.

Verifica:
- dry-run non elimina nulla;
- execute elimina solo le entita' di test;
- le entita' di controllo restano intatte.
"""

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.core.config import settings
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.db.therapy_models import Medicine, Reminder, Therapy
from app.services.document_delete import delete_document_and_file
from app.services.family import ensure_family_and_self_patient

from cleanup_test_data import execute_cleanup, find_candidates

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")

TEST_TITLE_PREFIX = "CLEANUP TEST"
TEST_MARKER = "cleanup-test-micro-step"
TEST_STORAGE_PREFIX = "_fixtures/cleanup-test-"

CONTROL_TITLE_PREFIX = "CONTROL CLEANUP"
CONTROL_MARKER = "control-cleanup-micro-step"
CONTROL_STORAGE_PREFIX = "_fixtures/control-cleanup-"

failures: list[str] = []

db = None

test_doc_id = None
control_doc_id = None

test_lab_id = None
control_lab_id = None

test_med_id = None
control_med_id = None

test_therapy_id = None
control_therapy_id = None

test_reminder_id = None
control_reminder_id = None

test_path = None
control_path = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


def _create_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% cleanup test data\n" + b"w" * 80)


def _make_document(db, user, patient, title: str, storage_key: str):
    path = LOCAL_STORAGE_ROOT / storage_key
    _create_pdf(path)

    document = Document(
        patient_id=patient.id,
        uploaded_by_user_id=user.id,
        title=title,
        document_type="lab_report",
        source_filename=path.name,
        storage_key=storage_key,
        mime_type="application/pdf",
        size_bytes=path.stat().st_size,
        sha256="0" * 64,
        processing_status="completed",
        ai_status="disabled",
        metadata_json={"cleanup_test_data": True},
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document, path


def _make_lab(db, document, patient, code: str, name: str):
    lab = LabTest(
        document_id=document.id,
        patient_id=patient.id,
        test_code=code,
        test_name_original=name,
        test_name_normalized=name.lower(),
        value_numeric=Decimal("1.0000"),
        unit="u",
        reference_min=Decimal("0.0000"),
        reference_max=Decimal("2.0000"),
        reference_text="0 - 2",
        flag="normal",
        confirmed_by_user=True,
        user_corrected=False,
        extracted_at=datetime.now(timezone.utc),
    )

    db.add(lab)
    db.commit()
    db.refresh(lab)

    return lab


def _make_medicine(db, user, patient, name: str, notes: str):
    medicine = Medicine(
        patient_id=patient.id,
        name=name,
        generic_name="Test",
        form="compressa",
        strength="1 mg",
        notes=notes,
        created_by_user_id=user.id,
    )

    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    return medicine


def _make_therapy(db, user, patient, medicine, document, notes: str, instructions: str, prescribed_by: str):
    therapy = Therapy(
        patient_id=patient.id,
        medicine_id=medicine.id,
        status="active",
        start_date=date.today(),
        end_date=None,
        frequency="once_daily",
        dose="1 compressa",
        route="orale",
        instructions=instructions,
        prescribed_by=prescribed_by,
        prescription_document_id=document.id,
        notes=notes,
        created_by_user_id=user.id,
    )

    db.add(therapy)
    db.commit()
    db.refresh(therapy)

    return therapy


def _make_reminder(db, user, patient, therapy, title: str, notes: str):
    reminder = Reminder(
        patient_id=patient.id,
        therapy_id=therapy.id,
        title=title,
        reminder_type="medication",
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="pending",
        notes=notes,
        created_by_user_id=user.id,
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return reminder


def _contains_id(rows, obj_id) -> bool:
    return any(str(row.id) == str(obj_id) for row in rows)


def _present(db, model, obj_id) -> bool:
    if obj_id is None:
        return False
    db.expire_all()
    return db.get(model, obj_id) is not None


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

        test_doc, test_path = _make_document(
            db,
            user,
            patient,
            title=f"{TEST_TITLE_PREFIX} doc {RUN_ID}",
            storage_key=f"{TEST_STORAGE_PREFIX}{RUN_ID}.pdf",
        )

        control_doc, control_path = _make_document(
            db,
            user,
            patient,
            title=f"{CONTROL_TITLE_PREFIX} doc {RUN_ID}",
            storage_key=f"{CONTROL_STORAGE_PREFIX}{RUN_ID}.pdf",
        )

        test_lab = _make_lab(
            db,
            test_doc,
            patient,
            code=f"cleanup_test_{RUN_ID}",
            name=f"{TEST_TITLE_PREFIX} LAB {RUN_ID}",
        )

        control_lab = _make_lab(
            db,
            control_doc,
            patient,
            code=f"control_cleanup_{RUN_ID}",
            name=f"{CONTROL_TITLE_PREFIX} LAB {RUN_ID}",
        )

        test_med = _make_medicine(
            db,
            user,
            patient,
            name=f"{TEST_TITLE_PREFIX} med {RUN_ID}",
            notes=TEST_MARKER,
        )

        control_med = _make_medicine(
            db,
            user,
            patient,
            name=f"{CONTROL_TITLE_PREFIX} med {RUN_ID}",
            notes=CONTROL_MARKER,
        )

        test_therapy = _make_therapy(
            db,
            user,
            patient,
            test_med,
            test_doc,
            notes=TEST_MARKER,
            instructions="Cleanup test therapy.",
            prescribed_by="Cleanup test",
        )

        control_therapy = _make_therapy(
            db,
            user,
            patient,
            control_med,
            control_doc,
            notes=CONTROL_MARKER,
            instructions="Control cleanup therapy.",
            prescribed_by="Control cleanup",
        )

        test_reminder = _make_reminder(
            db,
            user,
            patient,
            test_therapy,
            title=f"{TEST_TITLE_PREFIX} reminder {RUN_ID}",
            notes=TEST_MARKER,
        )

        control_reminder = _make_reminder(
            db,
            user,
            patient,
            control_therapy,
            title=f"{CONTROL_TITLE_PREFIX} reminder {RUN_ID}",
            notes=CONTROL_MARKER,
        )

        test_doc_id = test_doc.id
        control_doc_id = control_doc.id

        test_lab_id = test_lab.id
        control_lab_id = control_lab.id

        test_med_id = test_med.id
        control_med_id = control_med.id

        test_therapy_id = test_therapy.id
        control_therapy_id = control_therapy.id

        test_reminder_id = test_reminder.id
        control_reminder_id = control_reminder.id

        print("Setup creato:")
        print(f"  test_document_id={test_doc_id}")
        print(f"  control_document_id={control_doc_id}")
        print(f"  test_file={test_path}")
        print(f"  control_file={control_path}")
        print()

        candidates = find_candidates(db)

        check("test document in candidates", _contains_id(candidates["documents"], test_doc_id))
        check("control document not in candidates", not _contains_id(candidates["documents"], control_doc_id))

        check("test medicine in candidates", _contains_id(candidates["medicines"], test_med_id))
        check("control medicine not in candidates", not _contains_id(candidates["medicines"], control_med_id))

        check("test therapy in candidates", _contains_id(candidates["therapies"], test_therapy_id))
        check("control therapy not in candidates", not _contains_id(candidates["therapies"], control_therapy_id))

        check("test reminder in candidates", _contains_id(candidates["reminders"], test_reminder_id))
        check("control reminder not in candidates", not _contains_id(candidates["reminders"], control_reminder_id))

        check("test lab in candidates", _contains_id(candidates["lab_tests"], test_lab_id))
        check("control lab not in candidates", not _contains_id(candidates["lab_tests"], control_lab_id))

        stats, failed = execute_cleanup(db, candidates, execute=False)

        check("dry-run nessun fallimento", not failed, f"failed={failed}")

        check(
            "dry-run non elimina test document",
            _present(db, Document, test_doc_id),
        )
        check(
            "dry-run non elimina control document",
            _present(db, Document, control_doc_id),
        )
        check(
            "dry-run non elimina test file",
            test_path is not None and test_path.exists(),
        )
        check(
            "dry-run non elimina control file",
            control_path is not None and control_path.exists(),
        )

        candidates = find_candidates(db)
        stats, failed = execute_cleanup(db, candidates, execute=True)

        check("execute nessun fallimento", not failed, f"failed={failed}")

        check(
            "execute elimina test document",
            not _present(db, Document, test_doc_id),
        )
        check(
            "execute elimina test lab",
            not _present(db, LabTest, test_lab_id),
        )
        check(
            "execute elimina test medicine",
            not _present(db, Medicine, test_med_id),
        )
        check(
            "execute elimina test therapy",
            not _present(db, Therapy, test_therapy_id),
        )
        check(
            "execute elimina test reminder",
            not _present(db, Reminder, test_reminder_id),
        )
        check(
            "execute elimina test file",
            test_path is None or not test_path.exists(),
        )

        check(
            "execute conserva control document",
            _present(db, Document, control_doc_id),
        )
        check(
            "execute conserva control lab",
            _present(db, LabTest, control_lab_id),
        )
        check(
            "execute conserva control medicine",
            _present(db, Medicine, control_med_id),
        )
        check(
            "execute conserva control therapy",
            _present(db, Therapy, control_therapy_id),
        )
        check(
            "execute conserva control reminder",
            _present(db, Reminder, control_reminder_id),
        )
        check(
            "execute conserva control file",
            control_path is not None and control_path.exists(),
        )

    finally:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass

            try:
                for model, obj_id in (
                    (Reminder, test_reminder_id),
                    (Reminder, control_reminder_id),
                    (Therapy, test_therapy_id),
                    (Therapy, control_therapy_id),
                    (Medicine, test_med_id),
                    (Medicine, control_med_id),
                    (LabTest, test_lab_id),
                    (LabTest, control_lab_id),
                ):
                    if obj_id is None:
                        continue

                    obj = db.get(model, obj_id)
                    if obj is not None:
                        db.delete(obj)

                db.commit()
            except Exception as exc:  # noqa: BLE001
                print(f"WARN cleanup finale entita' fallito: {exc}")
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass

            try:
                for doc_id in (test_doc_id, control_doc_id):
                    if doc_id is None:
                        continue

                    doc = db.get(Document, doc_id)
                    if doc is not None:
                        delete_document_and_file(db, doc)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN cleanup finale documenti fallito: {exc}")
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass

            for path in (test_path, control_path):
                try:
                    if path is not None and path.exists():
                        path.unlink()
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

print("Tutti i test di igiene fixture/test data sono passati.")