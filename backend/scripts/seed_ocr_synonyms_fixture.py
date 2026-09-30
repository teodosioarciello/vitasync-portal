"""
Fixture di test Sprint 1.2b.
Genera un PDF SINTETICO con varianti OCR-like, senza usare OCR reale,
per verificare in modo deterministico la normalizzazione dei sinonimi.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/seed_ocr_synonyms_fixture.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import hashlib
import os
from datetime import date
from pathlib import Path

import fitz

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, User
from app.db.session import SessionLocal
from app.services.extraction import extract_from_document
from app.services.family import ensure_family_and_self_patient

STORAGE_ROOT = Path(settings.local_storage_path)

LINES = [
    "REFERTO SINTETICO SINONIMI OCR - DATI FICTIOUS",
    "ESAME VALORE UNITA RIFERIMENTO",
    "HBAIC 5.4 % 4.0 - 6.0",
    "GLUC0SIO 95 mg/dL 70 - 100",
    "GOT(AST) 22 U/L 0 - 35",
    "GOTAST 24 U/L 0 - 35",
    "CREATIN1NA 0.9 mg/dL 0.7 - 1.3",
    "L1PAS1 30 U/L 13 - 60",
    "TRIGL1CER1D1 120 mg/dL < 150",
    "COLESTEROL LDL 110 mg/dL < 130",
    "P0TASSI0 4.2 mmol/L 3.5 - 5.1",
    "V1TAMINA D 32 ng/mL 30 - 100",
]


def create_pdf(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    page = doc.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18

    doc.save(str(path))
    doc.close()


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            print("Nessun utente nel DB. Registra prima un account dal frontend.")
            return

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        storage_key = "_fixtures/ocr-synonyms-synthetic.pdf"
        pdf_path = STORAGE_ROOT / storage_key

        create_pdf(pdf_path, LINES)

        size = os.path.getsize(pdf_path)
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        document = Document(
            patient_id=patient.id,
            uploaded_by_user_id=user.id,
            title="Fixture sinonimi OCR sintetici",
            document_type="lab_report",
            source_filename="ocr-synonyms-synthetic.pdf",
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=size,
            sha256=sha,
            document_date=date.today(),
            processing_status="pending",
            ai_status="disabled",
            metadata_json={"ocr_synonym_fixture": True},
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        print(f"Documento fixture creato: id={document.id}")
        print(f"PDF salvato in: {pdf_path}")

        created = extract_from_document(db, document)
        db.refresh(document)

        meta = document.metadata_json or {}
        print(
            "extraction_source="
            f"{meta.get('extraction_source')} "
            "parser_version="
            f"{meta.get('parser_version')}"
        )
        print(f"Valori estratti (bozze): {len(created)}")

        for lt in created:
            val = lt.value_numeric if lt.value_numeric is not None else lt.value_text
            rng = ""
            if lt.reference_min is not None and lt.reference_max is not None:
                rng = f"{lt.reference_min}-{lt.reference_max}"
            elif lt.reference_max is not None:
                rng = f"< {lt.reference_max}"
            elif lt.reference_min is not None:
                rng = f"> {lt.reference_min}"

            conf = lt.confidence if lt.confidence is not None else 0.0

            print(
                f"  - {lt.test_name_normalized:<22} "
                f"original={lt.test_name_original:<18} "
                f"code={lt.test_code:<18} "
                f"val={val} {lt.unit or ''} "
                f"rif=[{rng}] flag={lt.flag} conf={conf:.2f}"
            )

        print()
        print("Per leggere via API (dopo login nel browser):")
        print(f"  GET /api/lab-tests?document_id={document.id}")
        print("Oppure da Swagger: http://localhost:8000/docs")
    finally:
        db.close()


if __name__ == "__main__":
    main()