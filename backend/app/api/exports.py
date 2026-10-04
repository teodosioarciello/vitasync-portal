"""
Sprint 5.3 - Export deterministico Markdown.
GET /api/exports/health-summary.md?patient_id=...&anonymize=true|false
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.models import Document, FamilyMember, LabTest, Patient
from app.db.therapy_models import Medicine, Therapy
from app.db.weight_models import WeightMeasurement
from app.deps import get_current_user, get_db
from app.services.health_alerts import build_health_summary
from app.services.health_export import build_markdown_export
from app.services.health_metrics import build_bmi_result, compute_age_years
from app.services.therapy_test_context import find_therapy_context_for_test

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _get_patient(patient_id: UUID, user, db: Session) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paziente non trovato.")
    member = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.family_id == patient.family_id,
            FamilyMember.user_id == user.id,
            FamilyMember.status == "active",
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Accesso negato a questo paziente.")
    return patient


@router.get("/health-summary.md")
def export_health_summary_md(
    patient_id: UUID = Query(...),
    anonymize: bool = Query(default=False),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)

    rows = (
        db.query(LabTest, Document)
        .join(Document, Document.id == LabTest.document_id)
        .filter(
            LabTest.patient_id == patient_id,
            LabTest.confirmed_by_user.is_(True),
            Document.deleted_at.is_(None),
        )
        .all()
    )
    confirmed_labs = []
    latest_document_date = None
    for lab, doc in rows:
        dd = doc.document_date or lab.created_at.date()
        if latest_document_date is None or dd > latest_document_date:
            latest_document_date = dd
        confirmed_labs.append({
            "test_code": lab.test_code,
            "test_name_normalized": lab.test_name_normalized,
            "value_numeric": float(lab.value_numeric) if lab.value_numeric is not None else None,
            "unit": lab.unit,
            "reference_min": float(lab.reference_min) if lab.reference_min is not None else None,
            "reference_max": float(lab.reference_max) if lab.reference_max is not None else None,
            "reference_text": lab.reference_text,
            "flag": lab.flag,
            "document_date": dd,
            "document_title": doc.title,
        })

    therapies = []
    active_therapies = (
        db.query(Therapy)
        .filter(Therapy.patient_id == patient_id, Therapy.status == "active")
        .all()
    )
    for t in active_therapies:
        med = db.get(Medicine, t.medicine_id) if t.medicine_id else None
        therapies.append({
            "medicine_name": med.name if med else "n/d",
            "generic_name": med.generic_name if med else None,
            "dose": t.dose,
            "frequency": t.frequency,
            "start_date": t.start_date,
            "status": t.status,
        })
    active_medicines = [
        {"name": t["medicine_name"], "generic_name": t["generic_name"]}
        for t in therapies
    ]

    weights_rows = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient_id)
        .order_by(WeightMeasurement.measured_at.desc())
        .limit(50)
        .all()
    )
    weights = [
        {"weight_kg": float(w.weight_kg), "measured_at": w.measured_at}
        for w in weights_rows
    ]

    weight_kg = weights[0]["weight_kg"] if weights else None
    height_cm = float(patient.height_cm) if patient.height_cm is not None else None
    bmi_result = build_bmi_result(
        weight_kg=weight_kg,
        height_cm=height_cm,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )

    summary = build_health_summary(
        patient={"id": patient.id},
        confirmed_labs=confirmed_labs,
        latest_document_date=latest_document_date,
        bmi_result=bmi_result,
        active_medicines=active_medicines,
        therapy_context_fn=find_therapy_context_for_test,
    )

    md = build_markdown_export(
        patient={
            "display_name": patient.display_name,
            "sex": patient.sex,
            "birth_date": patient.birth_date,
            "is_minor": patient.is_minor,
            "height_cm": height_cm,
            "age_years": compute_age_years(patient.birth_date),
        },
        confirmed_labs=confirmed_labs,
        therapies=therapies,
        weights=weights,
        bmi_result=bmi_result,
        summary=summary,
        anonymize=anonymize,
        generated_at=datetime.now(timezone.utc),
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = ("vitasync-export-pseudonimizzato-" if anonymize else "vitasync-export-") + ts + ".md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="' + fname + '"'},
    )