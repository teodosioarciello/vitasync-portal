import sys
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.db.models import User, Document, LabTest
from app.services.family import ensure_family_and_self_patient
from app.services.health_alerts import evaluate_lab_alert

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == "teo.test").first()
    _, patient = ensure_family_and_self_patient(db, user)

    # 1. Verifica documenti fixture trend
    print("=== DOCUMENTI FIXTURE TREND ===")
    fx_docs = (
        db.query(Document)
        .filter(Document.patient_id == patient.id, Document.title.like("Fixture trend%"))
        .all()
    )
    for d in fx_docs:
        print(f"{d.title} | deleted_at={d.deleted_at} | doc_date={d.document_date}")

    # 2. Raccogli tutti i valori confermati attivi
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

    # 3. Raggruppa per test_code e trova l'ultimo
    by_code = defaultdict(list)
    for lab, doc in rows:
        dd = doc.document_date or lab.created_at.date()
        by_code[lab.test_code].append({
            "date": dd,
            "value": lab.value_numeric,
            "flag": lab.flag,
            "doc_title": doc.title,
        })

    print("\n=== ULTIMI VALORI PER TEST_CODE ===")
    for code, points in sorted(by_code.items()):
        sorted_pts = sorted(points, key=lambda p: p["date"])
        last = sorted_pts[-1]
        print(f"{code:20} | data={last['date']} | valore={last['value']} | flag={last['flag']} | doc={last['doc_title'][:30]}")

        # Verifica se genererebbe alert
        alert = evaluate_lab_alert({
            "test_code": code,
            "test_name_normalized": code,
            "value_numeric": float(last["value"]) if last["value"] else None,
            "flag": last["flag"],
            "document_date": last["date"],
        })
        if alert:
            print(f"  -> ALERT: {alert['rule_id']} ({alert['severity']})")
        else:
            print(f"  -> nessun alert")

finally:
    db.close()