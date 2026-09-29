from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import Document, LabTest, User
from app.deps import get_current_user, get_db
from app.schemas.lab_test import LabTestOut
from app.services.family import ensure_family_and_self_patient

from app.api.documents import get_authorized_patient  # riuso l'autorizzazione

router = APIRouter(prefix="/api/lab-tests", tags=["lab-tests"])


@router.get("", response_model=list[LabTestOut])
def list_lab_tests(
    document_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if document_id is None and patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fornisci document_id oppure patient_id.",
        )

    if document_id is not None:
        document = db.get(Document, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documento non trovato.",
            )
        get_authorized_patient(document.patient_id, current_user, db, required_permission="read")
        query = db.query(LabTest).filter(LabTest.document_id == document_id)
    else:
        get_authorized_patient(patient_id, current_user, db, required_permission="read")
        query = db.query(LabTest).filter(LabTest.patient_id == patient_id)

    rows = query.order_by(LabTest.test_name_normalized.asc()).all()
    return [LabTestOut.model_validate(r) for r in rows]