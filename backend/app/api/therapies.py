from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.documents import get_authorized_patient
from app.db.models import User
from app.db.therapy_models import Therapy
from app.deps import get_current_user, get_db
from app.schemas.therapy import (
    ALLOWED_THERAPY_FREQUENCIES,
    ALLOWED_THERAPY_STATUSES,
    TherapyCreate,
    TherapyOut,
    TherapyUpdate,
)
from app.services.family import ensure_family_and_self_patient
from app.services.therapy import (
    get_authorized_therapy,
    validate_document_for_patient,
    validate_medicine_for_patient,
    validate_therapy_dates,
)

router = APIRouter(prefix="/api/therapies", tags=["therapies"])


@router.get("", response_model=list[TherapyOut])
def list_therapies(
    patient_id: UUID | None = Query(None),
    therapy_status: str | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
    else:
        patient = get_authorized_patient(
            patient_id, current_user, db, required_permission="read"
        )

    if therapy_status is not None and therapy_status not in ALLOWED_THERAPY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stato terapia non valido.",
        )

    query = db.query(Therapy).filter(Therapy.patient_id == patient.id)

    if therapy_status is not None:
        query = query.filter(Therapy.status == therapy_status)

    rows = query.order_by(Therapy.created_at.desc()).all()
    return [TherapyOut.model_validate(row) for row in rows]


@router.post("", response_model=TherapyOut)
def create_therapy(
    payload: TherapyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = get_authorized_patient(
        payload.patient_id, current_user, db, required_permission="write"
    )

    if payload.status not in ALLOWED_THERAPY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stato terapia non valido.",
        )

    if payload.frequency not in ALLOWED_THERAPY_FREQUENCIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Frequenza terapia non valida.",
        )

    validate_therapy_dates(payload.start_date, payload.end_date)

    medicine = validate_medicine_for_patient(
        payload.medicine_id, patient.id, db
    )

    if payload.prescription_document_id is not None:
        validate_document_for_patient(
            payload.prescription_document_id, patient.id, db
        )

    therapy = Therapy(
        patient_id=patient.id,
        medicine_id=medicine.id,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        frequency=payload.frequency,
        dose=payload.dose,
        route=payload.route,
        instructions=payload.instructions,
        prescribed_by=payload.prescribed_by,
        prescription_document_id=payload.prescription_document_id,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )

    db.add(therapy)
    db.commit()
    db.refresh(therapy)

    return TherapyOut.model_validate(therapy)


@router.get("/{therapy_id}", response_model=TherapyOut)
def get_therapy(
    therapy_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    therapy = get_authorized_therapy(
        therapy_id, current_user, db, required_permission="read"
    )
    return TherapyOut.model_validate(therapy)


@router.patch("/{therapy_id}", response_model=TherapyOut)
def update_therapy(
    therapy_id: UUID,
    payload: TherapyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    therapy = get_authorized_therapy(
        therapy_id, current_user, db, required_permission="write"
    )

    data = payload.model_dump(exclude_unset=True)

    if "medicine_id" in data:
        if data["medicine_id"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Medicinale non valido.",
            )
        validate_medicine_for_patient(data["medicine_id"], therapy.patient_id, db)

    if "prescription_document_id" in data and data["prescription_document_id"] is not None:
        validate_document_for_patient(
            data["prescription_document_id"], therapy.patient_id, db
        )

    if "status" in data:
        if data["status"] not in ALLOWED_THERAPY_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stato terapia non valido.",
            )

    if "frequency" in data:
        if data["frequency"] not in ALLOWED_THERAPY_FREQUENCIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Frequenza terapia non valida.",
            )

    start_date = data.get("start_date", therapy.start_date)
    end_date = data.get("end_date", therapy.end_date)
    validate_therapy_dates(start_date, end_date)

    for key, value in data.items():
        setattr(therapy, key, value)

    db.commit()
    db.refresh(therapy)

    return TherapyOut.model_validate(therapy)