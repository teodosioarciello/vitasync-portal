from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.documents import get_authorized_patient
from app.db.models import User
from app.db.therapy_models import Medicine, Therapy
from app.deps import get_current_user, get_db
from app.schemas.auth import MessageResponse
from app.schemas.therapy import MedicineCreate, MedicineOut, MedicineUpdate
from app.services.audit_identity import mark_audit_user
from app.services.family import ensure_family_and_self_patient
from app.services.therapy import get_authorized_medicine

router = APIRouter(prefix="/api/medicines", tags=["medicines"])


@router.get("", response_model=list[MedicineOut])
def list_medicines(
    patient_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
    else:
        patient = get_authorized_patient(
            patient_id, current_user, db, required_permission="read"
        )

    rows = (
        db.query(Medicine)
        .filter(Medicine.patient_id == patient.id)
        .order_by(Medicine.name.asc())
        .all()
    )

    return [MedicineOut.model_validate(row) for row in rows]


@router.post("", response_model=MedicineOut)
def create_medicine(
    request: Request,
    payload: MedicineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    patient = get_authorized_patient(
        payload.patient_id, current_user, db, required_permission="write"
    )

    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome medicinale non valido.",
        )

    medicine = Medicine(
        patient_id=patient.id,
        name=name,
        generic_name=payload.generic_name,
        form=payload.form,
        strength=payload.strength,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )

    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    return MedicineOut.model_validate(medicine)


@router.get("/{medicine_id}", response_model=MedicineOut)
def get_medicine(
    medicine_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    medicine = get_authorized_medicine(
        medicine_id, current_user, db, required_permission="read"
    )
    return MedicineOut.model_validate(medicine)


@router.patch("/{medicine_id}", response_model=MedicineOut)
def update_medicine(
    request: Request,
    medicine_id: UUID,
    payload: MedicineUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    medicine = get_authorized_medicine(
        medicine_id, current_user, db, required_permission="write"
    )

    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        if data["name"] is None or not str(data["name"]).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome medicinale non valido.",
            )
        data["name"] = str(data["name"]).strip()

    for key, value in data.items():
        setattr(medicine, key, value)

    db.commit()
    db.refresh(medicine)

    return MedicineOut.model_validate(medicine)


@router.delete("/{medicine_id}", response_model=MessageResponse)
def delete_medicine(
    request: Request,
    medicine_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    medicine = get_authorized_medicine(
        medicine_id, current_user, db, required_permission="write"
    )

    therapy_exists = (
        db.query(Therapy.id)
        .filter(Therapy.medicine_id == medicine.id)
        .first()
    )

    if therapy_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossibile eliminare un medicinale usato in almeno una terapia.",
        )

    db.delete(medicine)
    db.commit()

    return MessageResponse(detail="Medicinale eliminato.")