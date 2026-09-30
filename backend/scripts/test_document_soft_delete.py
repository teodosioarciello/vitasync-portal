"""
Test deterministico Sprint C-media Step 6A.
Verifica soft-delete, restore e permanent-delete a livello servizio.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_document_soft_delete.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import hashlib
from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.db.therapy_models import Medicine, Therapy
from app.services.document_delete import (
    delete_document_and_file,
    permanent_delete_document,
    restore_document,
    soft_delete_document,
)
from app.services.family import ensure_family_and_self_patient

STORAGE_ROOT = Path(settings.local_storage_path)
STORAGE_KEY = "_fixtures/test-soft-delete-document.pdf"
TITLE = "TEST C-media soft delete document"
MED_NAME = "TEST C-media soft delete medicine"
MARKER = "c-media-soft-delete-test"


def create_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = b"%PDF-1.4\n% synthetic soft delete test\n" + b"x" * 120
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
            source_filename="test-soft-delete-document.pdf",
            storage_key=STORAGE_KEY,
            mime_type="application/pdf",
            size_bytes=size,
            sha256=sha,
            document_date=date.today(),
            processing_status="completed",
            ai_status="disabled",
            metadata_json={"soft_delete_test": True},
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        lab = LabTest(
            document_id=document.id,
            patient_id=patient.id,
            test_code="test_soft_delete",
            test_name_original="TEST SOFT DELETE",
            test_name_normalized="Test soft delete",
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
            instructions="Test soft delete flow.",
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

        # 1. Soft delete
        changed = soft_delete_document(db, document)
        db.expire_all()

        doc = db.get(Document, document_id)
        lab_after = db.get(LabTest, lab_id)
        therapy_after = db.get(Therapy, therapy_id)
        file_exists = pdf_path.exists()

        active = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )

        trash = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.isnot(None),
            )
            .first()
        )

        print("Verifiche post soft-delete:")
        print(f"  soft_delete cambiato: {changed}")
        print(f"  documento presente: {doc is not None}")
        print(f"  deleted_at popolato: {doc is not None and doc.deleted_at is not None}")
        print(f"  lab_test ancora presente: {lab_after is not None}")
        print(f"  terapia ancora collegata: {therapy_after is not None and therapy_after.prescription_document_id == document_id}")
        print(f"  file ancora presente: {file_exists}")
        print(f"  assente da lista attiva: {active is None}")
        print(f"  presente in trash: {trash is not None}")
        print()

        if not changed:
            failures.append("soft_delete_document non ha riportato cambiamento.")
        if doc is None or doc.deleted_at is None:
            failures.append("Documento non marcato come cancellato.")
        if lab_after is None:
            failures.append("LabTest scomparsa inaspettatamente dopo soft-delete.")
        if therapy_after is None or therapy_after.prescription_document_id != document_id:
            failures.append("Terapia non piu' collegata dopo soft-delete.")
        if not file_exists:
            failures.append("File fisico eliminato inaspettatamente dopo soft-delete.")
        if active is not None:
            failures.append("Documento ancora visibile nella lista attiva.")
        if trash is None:
            failures.append("Documento non visibile nel trash.")

        # 2. Restore
        if doc is not None:
            changed_restore = restore_document(db, doc)
        else:
            changed_restore = False
            failures.append("Documento mancante prima del restore.")

        db.expire_all()

        doc = db.get(Document, document_id)
        active = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        trash = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.isnot(None),
            )
            .first()
        )

        print("Verifiche post-restore:")
        print(f"  restore cambiato: {changed_restore}")
        print(f"  deleted_at nullo: {doc is not None and doc.deleted_at is None}")
        print(f"  presente in lista attiva: {active is not None}")
        print(f"  assente da trash: {trash is None}")
        print()

        if not changed_restore:
            failures.append("restore_document non ha riportato cambiamento.")
        if doc is None or doc.deleted_at is not None:
            failures.append("Documento non ripristinato correttamente.")
        if active is None:
            failures.append("Documento non torna nella lista attiva dopo restore.")
        if trash is not None:
            failures.append("Documento ancora nel trash dopo restore.")

        # 3. Permanent delete su documento attivo deve essere rifiutata
        if doc is not None:
            try:
                permanent_delete_document(db, doc)
                failures.append("Permanent delete su documento attivo non ha sollevato errore.")
            except HTTPException as exc:
                if exc.status_code != 400:
                    failures.append(
                        f"Permanent delete su documento attivo: atteso HTTP 400, ricevuto {exc.status_code}"
                    )
                else:
                    print("OK permanent delete su documento attivo rifiutata con HTTP 400.")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"Permanent delete su documento attivo: eccezione inattesa {exc!r}")

        print()

        # 4. Soft delete finale + permanent delete
        doc = db.get(Document, document_id)

        if doc is None:
            failures.append("Documento scomparso prima del permanent delete finale.")
        else:
            soft_delete_document(db, doc)
            db.expire_all()

            doc = db.get(Document, document_id)

            if doc is None or doc.deleted_at is None:
                failures.append("Soft delete finale non applicato.")
            else:
                permanent_delete_document(db, doc)
                db.expire_all()

                doc_after = db.get(Document, document_id)
                lab_final = db.get(LabTest, lab_id)
                therapy_final = db.get(Therapy, therapy_id)
                file_final = pdf_path.exists()

                print("Verifiche post permanent-delete:")
                print(f"  documento assente: {doc_after is None}")
                print(f"  lab_test assente: {lab_final is None}")
                print(f"  terapia ancora presente: {therapy_final is not None}")
                print(
                    "  terapia prescription_document_id null: "
                    f"{therapy_final is not None and therapy_final.prescription_document_id is None}"
                )
                print(f"  file assente: {not file_final}")
                print()

                if doc_after is not None:
                    failures.append("Documento ancora presente dopo permanent-delete.")
                if lab_final is not None:
                    failures.append("LabTest ancora presente dopo permanent-delete.")
                if therapy_final is None:
                    failures.append("Terapia scomparsa inaspettatamente dopo permanent-delete.")
                elif therapy_final.prescription_document_id is not None:
                    failures.append("Terapia ancora collegata dopo permanent-delete.")
                if file_final:
                    failures.append("File fisico ancora presente dopo permanent-delete.")

        # Cleanup terapia/medicine di test
        therapy_final = db.get(Therapy, therapy_id)
        if therapy_final is not None:
            db.delete(therapy_final)

        medicine_final = db.get(Medicine, medicine_id)
        if medicine_final is not None:
            db.delete(medicine_final)

        db.commit()

        if failures:
            print("TEST FALLITI:")
            for failure in failures:
                print(f"  - {failure}")
            return 1

        print("Tutti i test di soft-delete/restore/permanent-delete sono passati.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())