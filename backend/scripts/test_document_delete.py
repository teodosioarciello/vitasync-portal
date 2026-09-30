"""
Test deterministico Sprint C-media Step 2.
Verifica che la cancellazione documento rimuova:
- documento;
- lab_tests collegate;
- riferimento terapia al documento;
- file fisico, se presente.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_document_delete.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import hashlib
from datetime import date, datetime, timezone

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.db.therapy_models import Medicine, Therapy
from app.services.document_delete import delete_document_and_file
from app.services.family import ensure_family_and_self_patient

STORAGE_ROOT = Path(settings.local_storage_path)
STORAGE_KEY = "_fixtures/test-delete-document.pdf"
TITLE = "TEST C-media delete document"
MED_NAME = "TEST C-media medicine"
MARKER = "c-media-delete-test"


def create_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = b"%PDF-1.4\n% synthetic test document\n" + b"x" * 120
    path.write_bytes(content)


def cleanup_previous(db) -> None:
    old_docs = (
        db.query(Document)
        .filter(
            (Document.storage_key == STORAGE_KEY)
            | (Document.title == TITLE)
        )
        .all()
    )

    for doc in old_docs:
        try:
            delete_document_and_file(db, doc)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup documento precedente fallito: {exc}")
            db.rollback()

    old_therapies = db.query(Therapy).filter(Therapy.notes == MARKER).all()
    for therapy in old_therapies:
        db.delete(therapy)

    old_medicines = (
        db.query(Medicine)
        .filter(
            Medicine.name == MED_NAME,
            Medicine.notes == MARKER,
        )
        .all()
    )
    for medicine in old_medicines:
        db.delete(medicine)

    db.commit()


def main() -> int:
    db = SessionLocal()
    failures: list[str] = []

    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            print("Nessun utente nel DB. Registra prima un account dal frontend.")
            return 1

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        cleanup_previous(db)

        pdf_path = STORAGE_ROOT / STORAGE_KEY
        create_pdf(pdf_path)

        size = pdf_path.stat().st_size
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        document = Document(
            patient_id=patient.id,
            uploaded_by_user_id=user.id,
            title=TITLE,
            document_type="lab_report",
            source_filename="test-delete-document.pdf",
            storage_key=STORAGE_KEY,
            mime_type="application/pdf",
            size_bytes=size,
            sha256=sha,
            document_date=date.today(),
            processing_status="completed",
            ai_status="disabled",
            metadata_json={"delete_test": True},
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        lab = LabTest(
            document_id=document.id,
            patient_id=patient.id,
            test_code="test_delete",
            test_name_original="TEST DELETE",
            test_name_normalized="Test delete",
            value_numeric=1.0,
            value_text=None,
            unit="u",
            reference_min=0.0,
            reference_max=2.0,
            reference_text="0 - 2",
            flag="normal",
            method=None,
            confidence=0.9,
            confirmed_by_user=False,
            user_corrected=False,
            notes=None,
            extracted_at=datetime.now(timezone.utc),
        )

        db.add(lab)
        db.commit()
        db.refresh(lab)

        medicine = Medicine(
            patient_id=patient.id,
            name=MED_NAME,
            generic_name="Test",
            form="compressa",
            strength="1 u",
            notes=MARKER,
            created_by_user_id=user.id,
        )

        db.add(medicine)
        db.commit()
        db.refresh(medicine)

        therapy = Therapy(
            patient_id=patient.id,
            medicine_id=medicine.id,
            status="active",
            start_date=date.today(),
            end_date=None,
            frequency="once_daily",
            dose="1 compressa",
            route="orale",
            instructions="Test delete flow.",
            prescribed_by="Medico fixture",
            prescription_document_id=document.id,
            notes=MARKER,
            created_by_user_id=user.id,
        )

        db.add(therapy)
        db.commit()
        db.refresh(therapy)

        document_id = document.id
        lab_id = lab.id
        therapy_id = therapy.id
        medicine_id = medicine.id

        print("Setup creato:")
        print(f"  document_id={document_id}")
        print(f"  lab_test_id={lab_id}")
        print(f"  therapy_id={therapy_id}")
        print(f"  medicine_id={medicine_id}")
        print(f"  file={pdf_path}")
        print()

        deleted_file = delete_document_and_file(db, document)

        db.expire_all()

        doc_after = db.get(Document, document_id)
        lab_after = db.get(LabTest, lab_id)
        therapy_after = db.get(Therapy, therapy_id)
        file_after_exists = pdf_path.exists()

        print("Verifiche post-delete:")
        print(f"  documento assente: {doc_after is None}")
        print(f"  lab_test assente: {lab_after is None}")
        print(f"  terapia ancora presente: {therapy_after is not None}")
        print(
            "  terapia prescription_document_id null: "
            f"{therapy_after is not None and therapy_after.prescription_document_id is None}"
        )
        print(f"  file assente: {not file_after_exists}")
        print(f"  file esisteva prima: {deleted_file}")
        print()

        if doc_after is not None:
            failures.append("Documento ancora presente nel DB dopo delete.")

        if lab_after is not None:
            failures.append("LabTest ancora presente nel DB dopo delete documento.")

        if therapy_after is None:
            failures.append("Terapia di test scomparsa in modo inatteso.")
        elif therapy_after.prescription_document_id is not None:
            failures.append("Terapia ancora collegata al documento eliminato.")

        if file_after_exists:
            failures.append("File fisico ancora presente dopo delete.")

        if not deleted_file:
            failures.append("Il file di test sarebbe dovuto esistere prima del delete.")

        # Cleanup finale terapia/medicine di test.
        if therapy_after is not None:
            db.delete(therapy_after)

        medicine_after = db.get(Medicine, medicine_id)
        if medicine_after is not None:
            db.delete(medicine_after)

        db.commit()

        if failures:
            print("TEST FALLITI:")
            for failure in failures:
                print(f"  - {failure}")
            return 1

        print("Tutti i test di cancellazione documento sono passati.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())