from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.models import (
    Document,
    FamilyMember,
    LabTest,
    Patient,
    PatientAccessGrant,
    User,
)
from app.deps import get_current_user, get_db
from app.schemas.auth import MessageResponse
from app.schemas.document import DocumentOut
from app.schemas.lab_test import ConfirmAllResponse, LabTestOut
from app.services.audit_identity import mark_audit_user
from app.services.document_delete import delete_document_and_file
from app.services.extraction import extract_from_document
from app.services.family import ensure_family_and_self_patient
from app.services.storage import save_document
from app.services.upload_validation import validate_upload_file

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_DOCUMENT_TYPES = {
    "lab_report",
    "urine_report",
    "prescription",
    "imaging",
    "medical_letter",
    "nutrition_report",
    "other",
}


def get_authorized_patient(
    patient_id: UUID,
    user: User,
    db: Session,
    required_permission: str = "read",
) -> Patient:
    patient = db.get(Patient, patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paziente non trovato.",
        )

    now = datetime.now(timezone.utc)

    grant = (
        db.query(PatientAccessGrant)
        .filter(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.user_id == user.id,
            (PatientAccessGrant.expires_at.is_(None))
            | (PatientAccessGrant.expires_at > now),
        )
        .first()
    )

    if grant:
        if required_permission == "read" and grant.permission in {"read", "write", "admin"}:
            return patient
        if required_permission == "write" and grant.permission in {"write", "admin"}:
            return patient
        if required_permission == "admin" and grant.permission == "admin":
            return patient

    member = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.family_id == patient.family_id,
            FamilyMember.user_id == user.id,
            FamilyMember.status == "active",
        )
        .first()
    )

    if member:
        if required_permission == "read" and member.role in {"owner", "admin", "member", "viewer"}:
            return patient
        if required_permission == "write" and member.role in {"owner", "admin", "member"}:
            return patient
        if required_permission == "admin" and member.role in {"owner", "admin"}:
            return patient

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Non hai permessi sufficienti su questo paziente.",
    )


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    request: Request,
    patient_id: UUID = Query(...),
    title: str = Form(...),
    document_type: str = Form(...),
    file=File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo documento non valido.",
        )

    detected_mime = validate_upload_file(file)

    patient = get_authorized_patient(
        patient_id,
        current_user,
        db,
        required_permission="write",
    )

    document = await save_document(
        db=db,
        patient_id=patient.id,
        uploaded_by_user_id=current_user.id,
        title=title,
        document_type=document_type,
        file=file,
    )

    if document.mime_type != detected_mime:
        document.mime_type = detected_mime
        db.commit()
        db.refresh(document)

    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    patient_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
        patient_id = patient.id

    patient = get_authorized_patient(
        patient_id,
        current_user,
        db,
        required_permission="read",
    )

    documents = (
        db.query(Document)
        .filter(Document.patient_id == patient.id)
        .order_by(Document.created_at.desc())
        .limit(100)
        .all()
    )

    return [DocumentOut.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento non trovato.",
        )

    get_authorized_patient(
        document.patient_id,
        current_user,
        db,
        required_permission="read",
    )
    return DocumentOut.model_validate(document)


@router.post("/{document_id}/extract", response_model=list[LabTestOut])
def extract_document(
    request: Request,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento non trovato.",
        )

    get_authorized_patient(
        document.patient_id,
        current_user,
        db,
        required_permission="read",
    )

    try:
        created = extract_from_document(db, document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        document.processing_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Estrazione fallita: {exc}",
        )

    return [LabTestOut.model_validate(lt) for lt in created]


@router.post("/{document_id}/lab-tests/confirm-all", response_model=ConfirmAllResponse)
def confirm_all_lab_tests(
    request: Request,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento non trovato.",
        )

    get_authorized_patient(
        document.patient_id,
        current_user,
        db,
        required_permission="write",
    )

    count = (
        db.query(LabTest)
        .filter(
            LabTest.document_id == document_id,
            LabTest.confirmed_by_user.is_(False),
        )
        .update({"confirmed_by_user": True}, synchronize_session=False)
    )
    db.commit()

    return ConfirmAllResponse(
        updated_count=count,
        detail=f"Confermati {count} valori estratti.",
    )


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    request: Request,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento non trovato.",
        )

    get_authorized_patient(
        document.patient_id,
        current_user,
        db,
        required_permission="write",
    )

    try:
        deleted_file = delete_document_and_file(db, document)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eliminazione documento fallita: {exc}",
        )

    detail = "Documento eliminato."
    if deleted_file:
        detail += " File rimosso dallo storage."
    else:
        detail += " File gia' assente nello storage."

    return MessageResponse(detail=detail)