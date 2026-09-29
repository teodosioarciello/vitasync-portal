"""
Fixture di test Sprint 1.1 Step 1.
Genera un PDF SINTETICO (nessun dato reale) in storage locale,
crea una riga Document nel DB e lancia l'estrazione.
Da eseguire dentro il container backend:
    docker compose exec backend python scripts/seed_fixture.py
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

import fitz  # PyMuPDF

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, User
from app.db.session import SessionLocal
from app.services.extraction import extract_from_document
from app.services.family import ensure_family_and_self_patient

LINES = [
    "REFERTO SINTETICO DI TEST - DATI FICTIOUS",
    "ESAME VALORE UNITA RIFERIMENTO",
    "GLUCOSIO 95 mg/dL 70 - 100",
    "GOT (AST) 22 U/L 0 - 35",
    "GPT (ALT) 18 U/L 0 - 40",
    "CREATININA 0.9 mg/dL 0.7 - 1.3",
    "eGFR 95 mL/min > 90",
    "HbA1c 5.4 % 4.0 - 6.0",
    "COLESTEROLO TOTALE 190 mg/dL < 200",
    "COLESTEROLO LDL 110 mg/dL < 130",
    "COLESTEROLO HDL 55 mg/dL > 40",
    "TRIGLICERIDI 120 mg/dL < 150",
    "LIPASI 30 U/L 13 - 60",
    "VES 8 mm/h 0 - 20",
    "PCR 0.3 mg/L 0 - 5",
    "EMOGLOBINA 14.5 g/dL 12.0 - 16.0",
    "LEUCOCITI 6.2 10^3/uL 4.0 - 10.0",
    "PIASTRINE 250 10^3/uL 150 - 400",
    "TSH 1.8 mIU/L 0.4 - 4.0",
    "VITAMINA D 32 ng/mL 30 - 100",
    "FERRITINA 120 ng/mL 30 - 300",
    "SODIO 140 mmol/L 135 - 145",
    "POTASSIO 4.2 mmol/L 3.5 - 5.1",
]


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            print("Nessun utente nel DB. Registra prima un account dal frontend.")
            return

        _, patient = ensure_family_and_self_patient(db, user)

        fixtures_dir = Path(settings.local_storage_path) / "_fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = fixtures_dir / "lab-report-synthetic.pdf"

        doc = fitz.open()
        page = doc.new_page()
        y = 72
        for line in LINES:
            page.insert_text((72, y), line, fontsize=11)
            y += 18
        doc.save(str(pdf_path))
        doc.close()

        size = os.path.getsize(pdf_path)
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        storage_key = "_fixtures/lab-report-synthetic.pdf"

        document = Document(
            patient_id=patient.id,
            uploaded_by_user_id=user.id,
            title="Fixture referto sintetico",
            document_type="lab_report",
            source_filename="lab-report-synthetic.pdf",
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=size,
            sha256=sha,
            document_date=date.today(),
            processing_status="pending",
            ai_status="disabled",
            metadata_json={"fixture": True},
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        print(f"Documento fixture creato: id={document.id}")
        print(f"PDF salvato in: {pdf_path}")

        created = extract_from_document(db, document)
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
            print(
                f"  - {lt.test_name_normalized:<22} "
                f"code={lt.test_code:<18} "
                f"val={val} {lt.unit or ''} "
                f"rif=[{rng}] flag={lt.flag}"
            )

        print("\nPer leggere via API (dopo login nel browser):")
        print(f"  GET /api/lab-tests?document_id={document.id}")
        print("Oppure da Swagger: http://localhost:8000/docs")
    finally:
        db.close()


if __name__ == "__main__":
    main()