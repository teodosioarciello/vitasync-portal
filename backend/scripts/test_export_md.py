import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.db.models import User, Document, LabTest
from app.db.therapy_models import Medicine, Therapy
from app.db.weight_models import WeightMeasurement
from app.services.family import ensure_family_and_self_patient
from app.services.health_alerts import build_health_summary
from app.services.health_export import build_markdown_export
from app.services.health_metrics import build_bmi_result, compute_age_years
from app.services.therapy_test_context import find_therapy_context_for_test

db = SessionLocal()
try:
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
            "reference_text": l.reference_text,
            "flag": l.flag,
            "document_date": dd,
            "document_title": doc.title,
        })

    therapies = []
    for t in db.query(Therapy).filter(Therapy.patient_id == patient.id, Therapy.status == "active").all():
        med = db.get(Medicine, t.medicine_id) if t.medicine_id else None
        therapies.append({
            "medicine_name": med.name if med else "n/d",
            "generic_name": med.generic_name if med else None,
            "dose": t.dose,
            "frequency": t.frequency,
            "start_date": t.start_date,
            "status": t.status,
        })

    weights = [
        {"weight_kg": float(w.weight_kg), "measured_at": w.measured_at}
        for w in db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient.id)
        .order_by(WeightMeasurement.measured_at.desc())
        .all()
    ]

    bmi = build_bmi_result(
        weight_kg=weights[0]["weight_kg"] if weights else None,
        height_cm=float(patient.height_cm) if patient.height_cm is not None else None,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )

    summary = build_health_summary(
        patient={"id": patient.id},
        confirmed_labs=labs,
        latest_document_date=latest,
        bmi_result=bmi,
        active_medicines=[{"name": t["medicine_name"], "generic_name": t["generic_name"]} for t in therapies],
        therapy_context_fn=find_therapy_context_for_test,
    )

    common = dict(
        patient={
            "display_name": patient.display_name,
            "sex": patient.sex,
            "birth_date": patient.birth_date,
            "is_minor": patient.is_minor,
            "height_cm": float(patient.height_cm) if patient.height_cm is not None else None,
            "age_years": compute_age_years(patient.birth_date),
        },
        confirmed_labs=labs,
        therapies=therapies,
        weights=weights,
        bmi_result=bmi,
        summary=summary,
        generated_at=datetime.now(timezone.utc),
    )

    md = build_markdown_export(anonymize=False, **common)
    md_anon = build_markdown_export(anonymize=True, **common)

    print("=== ANTEPRIMA EXPORT NOMINATIVO (prime righe) ===")
    print("\n".join(md.splitlines()[:22]))
    print("...")

    assert "## Profilo" in md
    assert "## Esami confermati (storico)" in md
    assert "## Segnali deterministici" in md
    assert "## Limiti di questo export" in md
    assert patient.display_name in md

    assert "Paziente 1" in md_anon
    assert patient.display_name not in md_anon
    assert "Fixture trend" not in md_anon
    print()
    print("OK: export nominativo e pseudonimizzato validi.")
finally:
    db.close()