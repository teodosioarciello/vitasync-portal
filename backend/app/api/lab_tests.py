from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import Document, LabTest, Patient, User
from app.deps import get_current_user, get_db
from app.schemas.lab_test import LabTestOut, LabTestUpdate
from app.services.extraction import compute_flag

from app.api.documents import get_authorized_patient  # riuso autorizzazione

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


@router.patch("/{lab_test_id}", response_model=LabTestOut)
def patch_lab_test(
    lab_test_id: UUID,
    payload: LabTestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lt = db.get(LabTest, lab_test_id)
    if not lt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Valore esame non trovato.",
        )

    patient = db.get(Patient, lt.patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paziente non trovato.",
        )

    get_authorized_patient(patient.id, current_user, db, required_permission="write")

    data = payload.model_dump(exclude_unset=True)

    # Rilevo se l'utente ha corretto un valore rispetto all'estratto corrente.
    corrected = False
    if "value_numeric" in data and data["value_numeric"] is not None:
        cur = None if lt.value_numeric is None else round(float(lt.value_numeric), 4)
        new = round(float(data["value_numeric"]), 4)
        if cur is None or abs(cur - new) > 1e-6:
            corrected = True
    if "value_text" in data and data["value_text"] is not None:
        if (lt.value_text or "") != data["value_text"]:
            corrected = True

    for key, value in data.items():
        if key == "confirmed":
            continue
        setattr(lt, key, value)

    if data.get("confirmed"):
        lt.confirmed_by_user = True
    if corrected:
        lt.user_corrected = True

    # Ricalcolo il flag dopo eventuali correzioni di valore/range.
    lt.flag = compute_flag(lt.value_numeric, lt.reference_min, lt.reference_max)

    db.commit()
    db.refresh(lt)
    return LabTestOut.model_validate(lt)