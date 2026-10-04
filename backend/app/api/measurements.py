"""
Sprint 5.1a + 5.1c - API misure antropometriche.
POST/GET weight measurements + GET/PUT patient height + GET bmi.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import FamilyMember, Patient
from app.db.weight_models import WeightMeasurement
from app.deps import get_current_user, get_db
from app.services.audit_identity import mark_audit_user
from app.services.health_metrics import build_bmi_result, compute_age_years

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class WeightIn(BaseModel):
    measured_at: date
    weight_kg: float = Field(gt=0, le=500)
    notes: str | None = None


class WeightOut(BaseModel):
    id: UUID
    patient_id: UUID
    measured_at: date
    weight_kg: float
    source: str
    notes: str | None
    created_at: str

    model_config = {"from_attributes": True}


class HeightIn(BaseModel):
    height_cm: float = Field(gt=0, le=300)


class HeightOut(BaseModel):
    patient_id: UUID
    height_cm: float | None

    model_config = {"from_attributes": True}


class BmiOut(BaseModel):
    patient_id: UUID
    bmi: float | None
    category: str | None
    category_it: str | None
    is_minor: bool
    has_sufficient_data: bool
    note: str | None
    weight_kg: float | None
    height_cm: float | None
    age_years: int | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_patient(patient_id: UUID, user, db: Session) -> Patient:
    """Verifica esistenza paziente + accesso via family membership."""
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


# ---------------------------------------------------------------------------
# Weight Measurements
# ---------------------------------------------------------------------------
@router.post("/weight", response_model=WeightOut)
def create_weight_measurement(
    request: Request,
    payload: WeightIn,
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)
    _get_patient(patient_id, current_user, db)

    measurement = WeightMeasurement(
        patient_id=patient_id,
        measured_at=payload.measured_at,
        weight_kg=payload.weight_kg,
        source="manual",
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    return WeightOut(
        id=measurement.id,
        patient_id=measurement.patient_id,
        measured_at=measurement.measured_at,
        weight_kg=float(measurement.weight_kg),
        source=measurement.source,
        notes=measurement.notes,
        created_at=measurement.created_at.isoformat(),
    )


@router.get("/weight", response_model=list[WeightOut])
def list_weight_measurements(
    patient_id: UUID = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_patient(patient_id, current_user, db)

    rows = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient_id)
        .order_by(WeightMeasurement.measured_at.desc())
        .limit(limit)
        .all()
    )
    return [
        WeightOut(
            id=r.id,
            patient_id=r.patient_id,
            measured_at=r.measured_at,
            weight_kg=float(r.weight_kg),
            source=r.source,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# BMI (calcolato da ultimo peso + altezza paziente)
# ---------------------------------------------------------------------------
@router.get("/bmi", response_model=BmiOut)
def get_bmi(
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)

    last_weight = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient_id)
        .order_by(WeightMeasurement.measured_at.desc())
        .first()
    )
    weight_kg = float(last_weight.weight_kg) if last_weight else None
    height_cm = float(patient.height_cm) if patient.height_cm is not None else None

    age = compute_age_years(patient.birth_date)

    result = build_bmi_result(
        weight_kg=weight_kg,
        height_cm=height_cm,
        birth_date=patient.birth_date,
        is_minor=bool(patient.is_minor),
    )

    return BmiOut(
        patient_id=patient.id,
        bmi=result["bmi"],
        category=result["category"],
        category_it=result["category_it"],
        is_minor=result["is_minor"],
        has_sufficient_data=result["has_sufficient_data"],
        note=result["note"],
        weight_kg=weight_kg,
        height_cm=height_cm,
        age_years=age,
    )


# ---------------------------------------------------------------------------
# Height (su Patient)
# ---------------------------------------------------------------------------
@router.get("/height", response_model=HeightOut)
def get_height(
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _get_patient(patient_id, current_user, db)
    h = float(patient.height_cm) if patient.height_cm is not None else None
    return HeightOut(patient_id=patient.id, height_cm=h)


@router.put("/height", response_model=HeightOut)
def update_height(
    request: Request,
    payload: HeightIn,
    patient_id: UUID = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)
    patient = _get_patient(patient_id, current_user, db)
    patient.height_cm = payload.height_cm
    db.commit()
    db.refresh(patient)
    return HeightOut(
        patient_id=patient.id,
        height_cm=float(patient.height_cm) if patient.height_cm is not None else None,
    )