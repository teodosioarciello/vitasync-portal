import argparse
import hashlib
import os
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import fitz

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.services.extraction import extract_from_document
from app.services.family import ensure_family_and_self_patient

STORAGE_ROOT = Path(settings.local_storage_path)

BASE_LINES = [
    "REFERTO SINTETICO TREND - DATI FICTIOUS",
    "ESAME VALORE UNITA RIFERIMENTO",
]

SCENARIOS = [
    {
        "label": "2026-01-baseline",
        "title": "Fixture trend Gennaio 2026",
        "document_date": date(2026, 1, 15),
        "lines": [
            "GLUCOSIO 95 mg/dL 70 - 100",
            "GOT (AST) 22 U/L 0 - 35",
            "HbA1c 5.4 % 4.0 - 6.0",
            "COLESTEROLO LDL 110 mg/dL < 130",
        ],
    },
    {
        "label": "2026-05-controllo",
        "title": "Fixture trend Maggio 2026",
        "document_date": date(2026, 5, 20),
        "lines": [
            "GLUCOSIO 112 mg/dL 70 - 100",
            "GOT (AST) 28 U/L 0 - 35",
            "HbA1c 5.9 % 4.0 - 6.0",
            "COLESTEROLO LDL 135 mg/dL < 130",
        ],
    },
    {
        "label": "2026-09-peggioramento",
        "title": "Fixture trend Settembre 2026",
        "document_date": date(2026, 9, 25),
        "lines": [
            "GLUCOSIO 180 mg/dL 70 - 100",
            "GOT (AST) 45 U/L 0 - 35",
            "HbA1c 6.8 % 4.0 - 6.0",
            "COLESTEROLO LDL 165 mg/dL < 130",
        ],
    },
]


def create_pdf(path: Path, lines: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18
    doc.save(str(path))
    doc.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.username:
            user = db.query(User).filter(User.username == args.username).first()
            if not user:
                print(f"Utente '{args.username}' non trovato.")
                return 1
        else:
            user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            print("Nessun utente nel DB.")
            return 1

        _, patient = ensure_family_and_self_patient(db, user)
        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")

        titles = [s["title"] for s in SCENARIOS]
        existing = (
            db.query(Document)
            .filter(
                Document.patient_id == patient.id,
                Document.title.in_(titles),
            )
            .count()
        )
        if existing > 0:
            print(f"Fixture trend gia' presente ({existing} documenti). Nessuna duplicazione.")
            return 0

        for scenario in SCENARIOS:
            storage_key = f"_fixtures/trend-{scenario['label']}.pdf"
            pdf_path = STORAGE_ROOT / storage_key
            lines = BASE_LINES + scenario["lines"]
            create_pdf(pdf_path, lines)
            size = os.path.getsize(pdf_path)
            sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            document = Document(
                patient_id=patient.id,
                uploaded_by_user_id=user.id,
                title=scenario["title"],
                document_type="lab_report",
                source_filename=f"trend-{scenario['label']}.pdf",
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=size,
                sha256=sha,
                document_date=scenario["document_date"],
                processing_status="pending",
                ai_status="disabled",
                metadata_json={"trend_fixture": True, "label": scenario["label"]},
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            created = extract_from_document(db, document)
            confirmed = (
                db.query(LabTest)
                .filter(LabTest.document_id == document.id)
                .update({"confirmed_by_user": True}, synchronize_session=False)
            )
            db.commit()
            print(f"Creato: {document.title} | valori={len(created)} confermati={confirmed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())