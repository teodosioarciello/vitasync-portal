from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.patient import PatientOut
from app.services.family import ensure_family_and_self_patient

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/me", response_model=PatientOut)
def get_my_patient(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, patient = ensure_family_and_self_patient(db, current_user)
    return PatientOut.model_validate(patient)
