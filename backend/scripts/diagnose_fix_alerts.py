import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from collections import Counter

from app.db.session import SessionLocal
from app.db.models import User, Document, LabTest
from app.db.weight_models import WeightMeasurement
from app.services.family import ensure_family_and_self_patient
from app.services.health_alerts import build_health_summary
from app.services.health_metrics import build_bmi_result
from app.services.therapy_test_context import find_therapy_context_for_test

USERNAME = sys.argv[1] if len(sys.argv) > 1 else "teo.test"

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == USERNAME).first()
    if not user:
        print("Utente non trovato:", USERNAME)
        raise SystemExit(1)
    _, patient = ensure_family_and_self_patient(db, user)
    print("Utente:", user.username, "| Paziente:", patient.id)

    print()
    print("--- DOCUMENTI FIXTURE TREND ---")
    fx = (
        db.query(Document)
        .filter(Document.patient_id == patient.id, Document.title.like("Fixture trend%"))
        .all()
    )
    for d in fx:
        n = db.query(LabTest).filter(LabTest.document_id == d.id).count()
        print(f"{d.title} | deleted_at={d.deleted_at} | doc_date={d.document_date} | labs={n}")

    trashed = [d.id for d in fx if d.deleted_at is not None]
    if trashed:
        print(f"RESTAURO {len(trashed)} documenti fixture dal cestino")
        db.query(Document).filter(Document.id.in_(trashed)).update(
            {Document.deleted_at: None}, synchronize_session=False
        )
        db.commit()
    else:
        print("Nessun documento fixture nel cestino.")

    def confirmed_rows():
        return (
            db.query(LabTest, Document)
            .join(Document, Document.id == LabTest.document_id)
            .filter(
                LabTest.patient_id == patient.id,
                LabTest.confirmed_by_user.is_(True),
                Document.deleted_at.is_(None),
            )
            .all()
        )

    rows = confirmed_rows()
    print()
    print("--- DISTRIBUZIONE FLAG (confermati attivi) ---")
    print(Counter(l.flag for l, _ in rows))

    fixed = 0
    for l, _ in rows:
        if (
            l.flag in (None, "unknown")
            and l.value_numeric is not None
            and (l.reference_min is not None or l.reference_max is not None)
        ):
            v = float(l.value_numeric)
            rmin = float(l.reference_min) if l.reference_min is not None else None
            rmax = float(l.reference_max) if l.reference_max is not None else None
            if rmax is not None and v > rmax:
                f = "above_range"
            elif rmin is not None and v < rmin:
                f = "below_range"
            else:
                f = "normal"
            l.flag = f
            fixed += 1
    db.commit()
    print("flag ricalcolati:", fixed)

    print()
    print("--- PUNTI FIXTURE (data, code, valore, flag, range) ---")
    for d in fx:
        labs = (
            db.query(LabTest)
            .filter(LabTest.document_id == d.id)
            .order_by(LabTest.test_code)
            .all()
        )
        for l in labs:
            print(d.document_date, l.test_code, l.value_numeric, l.flag, l.reference_min, l.reference_max)

    print()
    print("--- ALERT FINALI ---")
    rows = confirmed_rows()
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
    print("lab confermati:", len(labs))
    print("status:", s["status"])
    for a in s["alerts"]:
        print(" -", a.get("title_it"), "|", a["severity"])
finally:
    db.close()