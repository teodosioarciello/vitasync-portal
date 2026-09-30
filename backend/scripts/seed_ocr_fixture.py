"""
Fixture di test Sprint 1.2.
Genera un'immagine PNG SINTETICA con valori di laboratorio fictious,
la salva in storage locale, crea un Document nel DB e lancia l'estrazione OCR.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/seed_ocr_fixture.py
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

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.models import Document, User
from app.db.session import SessionLocal
from app.services.extraction import extract_from_document
from app.services.family import ensure_family_and_self_patient

STORAGE_ROOT = Path(settings.local_storage_path)

LINES = [
    "REFERTO SINTETICO OCR - DATI FICTIOUS",
    "ESAME VALORE UNITA RIFERIMENTO",
    "GLUCOSIO 95 mg/dL 70 - 100",
    "GOT AST 22 U/L 0 - 35",
    "CREATININA 0.9 mg/dL 0.7 - 1.3",
    "LIPASI 30 U/L 13 - 60",
    "HBA1C 5.4 % 4.0 - 6.0",
    "COLESTEROLO LDL 110 mg/dL 0 - 130",
]

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size: int):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def create_png(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    font = _load_font(32)
    margin = 60
    line_height = 52
    width = 1200
    height = margin * 2 + len(lines) * line_height

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    y = margin
    for line in lines:
        draw.text((margin, y), line, fill="black", font=font)
        y += line_height

    img.save(path, "PNG")


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

        storage_key = "_fixtures/ocr-lab-report-synthetic.png"
        pdf_path = STORAGE_ROOT / storage_key

        create_png(pdf_path, LINES)

        size = os.path.getsize(pdf_path)
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        document = Document(
            patient_id=patient.id,
            uploaded_by_user_id=user.id,
            title="Fixture OCR immagine sintetica",
            document_type="lab_report",
            source_filename="ocr-lab-report-synthetic.png",
            storage_key=storage_key,
            mime_type="image/png",
            size_bytes=size,
            sha256=sha,
            document_date=date.today(),
            processing_status="pending",
            ai_status="disabled",
            metadata_json={"ocr_fixture": True},
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        print(f"Documento fixture creato: id={document.id}")
        print(f"Immagine salvata in: {pdf_path}")

        created = extract_from_document(db, document)
        print(f"Valori estratti via OCR (bozze): {len(created)}")

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

        if len(created) == 0:
            print()
            print("ATTENZIONE: OCR non ha prodotto valori parseabili.")
            print("Controlla i log backend e la qualita' dell'immagine generata.")
        else:
            print()
            print("Ora apri la review del documento dal frontend oppure:")
            print(f"  GET /api/lab-tests?document_id={document.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()