import sys
from pathlib import Path
from datetime import date, datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.db.models import User, Document, LabTest
from app.db.weight_models import WeightMeasurement
from app.services.family import ensure_family_and_self_patient
from app.services.health_alerts import build_health_summary
from app.services.health_metrics import build_bmi_result
from app.services.therapy_test_context import find_therapy_context_for_test

CUTOFF_DATE = date(2026, 10, 1)

db = SessionLocal()
try:
    # 1. Cestina tutti i documenti con data >= CUTOFF_DATE
    docs_to_trash = (
        db.query(Document)
        .filter(
            Document.document_date >= CUTOFF_DATE,
            Document.deleted_at.is_(None),
        )
        .all()
    )
    
    now = datetime.now(timezone.utc)
    for d in docs_to_trash:
        d.deleted_at = now
    
    db.commit()
    print(f"Spostati nel cestino: {len(docs_to_trash)} documenti con data >= {CUTOFF_DATE}")
    for d in docs_to_trash[:10]:  # Mostra i primi 10
        print(f"  - {d.title} ({d.document_date})")
    if len(docs_to_trash) > 10:
        print(f"  ... e altri {len(docs_to_trash) - 10}")

    # 2. Verifica alert finali
    user = db.query(User).filter(User.username == "teo.test").first()
    _, patient = ensure_family_and_self_patient(db, user)

    rows = (
        db.query(LabTest, Document)
        .join(Document, Document.id == LabTest.document_id)
        .filter(
            LabTest.patient_id == patient.id,
            LabTest.confirmed_by_user.is_(True),
            Document.deleted_at.is_(None),
        )
        .all()
    )
    
    labs = []
    latest = None
    for l, doc in rows:
        dd = doc.document_date or l.created_at.date()
        if latest is None or dd > latest:
            latest = dd
        labs.append({
            "test_code": l.test_code,
            "test_name_normalized": l.test_name_normalized,
            "value_numeric": float(l.value_numeric) if l.value_numeric is not None else None,
            "unit": l.unit,
            "reference_min": float(l.reference_min) if l.reference_min is not None else None,
            "reference_max": float(l.reference_max) if l.reference_max is not None else None,
            "reference_text": l.reference_text,
            "flag": l.flag,
            "document_date": dd,
        })
    
    w = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient.id)
        .order_by(WeightMeasurement.measured_at.desc())
        .first()
    )
    bmi = build_bmi_result(
        weight_kg=float(w.weight_kg) if w else None,
        height_cm=float(patient.height_cm) if patient.height_cm is not None else None,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )
    
    s = build_health_summary(
        patient={"id": patient.id},
        confirmed_labs=labs,
        latest_document_date=latest,
        bmi_result=bmi,
        active_medicines=[],
        therapy_context_fn=find_therapy_context_for_test,
    )
    
    print()
    print("lab confermati attivi:", len(labs))
    print("status:", s["status"])
    print("alert:")
    for a in s["alerts"]:
        print(f"  - {a.get('title_it')} | {a['severity']}")
finally:
    db.close()