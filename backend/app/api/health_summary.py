"""
Sprint 5.2 - API Health Summary.
GET /api/health-summary?patient_id=...
Ritorna status + alert deterministici + note contesto terapie + missing data.
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
from app.services.health_metrics import build_bmi_result
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


@router.get("", response_model=HealthSummaryOut)
def get_health_summary(
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)

    # 1. Lab tests confermati da documenti attivi
    confirmed_labs_rows = (
        db.query(LabTest, Document)
        .join(Document, Document.id == LabTest.document_id)
        .filter(
            LabTest.patient_id == patient_id,
            LabTest.confirmed_by_user.is_(True),
            Document.deleted_at.is_(None),
        )
        .order_by(LabTest.extracted_at.asc(), LabTest.created_at.asc())
        .all()
    )

    confirmed_labs = []
    latest_document_date: date | None = None
    for lab, doc in confirmed_labs_rows:
        doc_date = doc.document_date or (lab.extracted_at or lab.created_at).date()
        if latest_document_date is None or doc_date > latest_document_date:
            latest_document_date = doc_date
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
            "document_date": doc_date,
        })

    # 2. BMI (ultimo peso + altezza)
    last_weight = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient_id)
        .order_by(WeightMeasurement.measured_at.desc())
        .first()
    )
    weight_kg = float(last_weight.weight_kg) if last_weight else None
    height_cm = float(patient.height_cm) if patient.height_cm is not None else None
    bmi_result = build_bmi_result(
        weight_kg=weight_kg,
        height_cm=height_cm,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )

    # 3. Medicinali da terapie attive
    active_therapies = (
        db.query(Therapy)
        .filter(
            Therapy.patient_id == patient_id,
            Therapy.status == "active",
        )
        .all()
    )
    medicine_ids = {t.medicine_id for t in active_therapies if t.medicine_id}
    active_medicines = []
    if medicine_ids:
        meds = db.query(Medicine).filter(Medicine.id.in_(medicine_ids)).all()
        active_medicines = [
            {"name": m.name, "generic_name": m.generic_name}
            for m in meds
        ]

    # 4. Build summary
    summary = build_health_summary(
        patient={"id": patient.id},
        confirmed_labs=confirmed_labs,
        latest_document_date=latest_document_date,
        bmi_result=bmi_result,
        active_medicines=active_medicines,
        therapy_context_fn=find_therapy_context_for_test,
    )

    return HealthSummaryOut(**summary)