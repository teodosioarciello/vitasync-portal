"""
Sprint 5.2 + 6.0 - API Health Summary.
GET  /api/health-summary            -> alert strutturati (5.2)
GET  /api/health-summary/narrative  -> sintesi narrativa deterministica (6.0)
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Document, FamilyMember, LabTest, Patient
from app.db.therapy_models import Medicine, Therapy
from app.db.weight_models import WeightMeasurement
from app.deps import get_current_user, get_db
from app.services.health_alerts import build_health_summary
from app.services.health_metrics import build_bmi_result, compute_age_years
from app.services.health_narrative import build_health_narrative
from app.services.therapy_test_context import find_therapy_context_for_test

router = APIRouter(prefix="/api/health-summary", tags=["health-summary"])


class HealthSummaryOut(BaseModel):
    status: str
    alerts: list[dict]
    therapy_context: list[dict]
    missing_data: list[str]
    patient_id: str
    generated_at: str

    model_config = {"from_attributes": True}


class NarrativeOut(BaseModel):
    patient_id: str
    status: str
    generated_at: str
    overview: str
    anthropometry: str
    labs: str
    therapies: str
    signals: list[str]
    questions_for_doctor: list[str]
    disclaimers: list[str]
    missing_data: list[str]

    model_config = {"from_attributes": True}


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


def _collect_data(patient: Patient, db: Session) -> dict:
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
    confirmed_labs = []
    latest_document_date = None
    for lab, doc in rows:
        dd = doc.document_date or lab.created_at.date()
        if latest_document_date is None or dd > latest_document_date:
            latest_document_date = dd
        confirmed_labs.append({
            "test_code": lab.test_code,
            "test_name_normalized": lab.test_name_normalized,
            "test_name_original": lab.test_name_original,
            "value_numeric": float(lab.value_numeric) if lab.value_numeric is not None else None,
            "value_text": lab.value_text,
            "unit": lab.unit,
            "reference_min": float(lab.reference_min) if lab.reference_min is not None else None,
            "reference_max": float(lab.reference_max) if lab.reference_max is not None else None,
            "reference_text": lab.reference_text,
            "flag": lab.flag,
            "document_date": dd,
        })

    last_weight = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient.id)
        .order_by(WeightMeasurement.measured_at.desc())
        .first()
    )
    weights_count = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient.id)
        .count()
    )
    weight_kg = float(last_weight.weight_kg) if last_weight else None
    height_cm = float(patient.height_cm) if patient.height_cm is not None else None
    bmi_result = build_bmi_result(
        weight_kg=weight_kg,
        height_cm=height_cm,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )

    active_therapies_rows = (
        db.query(Therapy)
        .filter(Therapy.patient_id == patient.id, Therapy.status == "active")
        .all()
    )
    active_therapies = []
    medicine_ids = set()
    for t in active_therapies_rows:
        if t.medicine_id:
            medicine_ids.add(t.medicine_id)
    meds_by_id = {}
    if medicine_ids:
        for m in db.query(Medicine).filter(Medicine.id.in_(medicine_ids)).all():
            meds_by_id[m.id] = m
    for t in active_therapies_rows:
        med = meds_by_id.get(t.medicine_id) if t.medicine_id else None
        active_therapies.append({
            "medicine_name": med.name if med else "n/d",
            "generic_name": med.generic_name if med else None,
            "dose": t.dose,
            "frequency": t.frequency,
            "start_date": t.start_date,
            "status": t.status,
        })
    active_medicines = [
        {"name": t["medicine_name"], "generic_name": t["generic_name"]}
        for t in active_therapies
    ]

    return {
        "patient": {
            "id": patient.id,
            "display_name": patient.display_name,
            "sex": patient.sex,
            "birth_date": patient.birth_date,
            "is_minor": patient.is_minor,
            "height_cm": height_cm,
            "age_years": compute_age_years(patient.birth_date),
        },
        "confirmed_labs": confirmed_labs,
        "latest_document_date": latest_document_date,
        "bmi_result": bmi_result,
        "active_therapies": active_therapies,
        "active_medicines": active_medicines,
        "weights_count": weights_count,
    }


@router.get("", response_model=HealthSummaryOut)
def get_health_summary(
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)
    d = _collect_data(patient, db)
    summary = build_health_summary(
        patient=d["patient"],
        confirmed_labs=d["confirmed_labs"],
        latest_document_date=d["latest_document_date"],
        bmi_result=d["bmi_result"],
        active_medicines=d["active_medicines"],
        therapy_context_fn=find_therapy_context_for_test,
    )
    return HealthSummaryOut(**summary)


@router.get("/narrative", response_model=NarrativeOut)
def get_health_narrative(
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)
    d = _collect_data(patient, db)
    summary = build_health_summary(
        patient=d["patient"],
        confirmed_labs=d["confirmed_labs"],
        latest_document_date=d["latest_document_date"],
        bmi_result=d["bmi_result"],
        active_medicines=d["active_medicines"],
        therapy_context_fn=find_therapy_context_for_test,
    )
    narrative = build_health_narrative(
        patient=d["patient"],
        summary=summary,
        bmi_result=d["bmi_result"],
        active_therapies=d["active_therapies"],
        weights_count=d["weights_count"],
        confirmed_labs_count=len(d["confirmed_labs"]),
    )
    return NarrativeOut(**narrative)