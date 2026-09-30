from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.models import Document, LabTest, Patient, User
from app.deps import get_current_user, get_db
from app.schemas.lab_test import (
    LabTestCodeSummary,
    LabTestOut,
    LabTestUpdate,
    TrendPoint,
    TrendResponse,
)
from app.services.audit_identity import mark_audit_user
from app.services.extraction import compute_flag
from app.services.family import ensure_family_and_self_patient

from app.api.documents import get_authorized_patient

router = APIRouter(prefix="/api/lab-tests", tags=["lab-tests"])

_MIN_DATE = date(1970, 1, 1)


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _effective_date(lt: LabTest, doc: Document | None) -> date | None:
    if doc is not None and doc.document_date is not None:
        return doc.document_date
    if lt.extracted_at is not None:
        return lt.extracted_at.date()
    if lt.created_at is not None:
        return lt.created_at.date()
    return None


def _date_sort_key(d: date | None):
    return (d is None, d or _MIN_DATE)


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
        if not document or document.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documento non trovato.",
            )

        get_authorized_patient(document.patient_id, current_user, db, required_permission="read")
        query = db.query(LabTest).filter(LabTest.document_id == document_id)
    else:
        get_authorized_patient(patient_id, current_user, db, required_permission="read")
        query = (
            db.query(LabTest)
            .join(Document, LabTest.document_id == Document.id)
            .filter(
                LabTest.patient_id == patient_id,
                Document.deleted_at.is_(None),
            )
        )

    rows = query.order_by(LabTest.test_name_normalized.asc()).all()
    return [LabTestOut.model_validate(r) for r in rows]


@router.patch("/{lab_test_id}", response_model=LabTestOut)
def patch_lab_test(
    request: Request,
    lab_test_id: UUID,
    payload: LabTestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_audit_user(request, current_user.id)

    lt = db.get(LabTest, lab_test_id)
    if not lt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Valore esame non trovato.",
        )

    document = db.get(Document, lt.document_id)
    if not document or document.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il documento collegato e' nel cestino o non disponibile.",
        )

    patient = db.get(Patient, lt.patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paziente non trovato.",
        )

    get_authorized_patient(patient.id, current_user, db, required_permission="write")

    data = payload.model_dump(exclude_unset=True)

    corrected = False

    if "value_numeric" in data and data["value_numeric"] is not None:
        cur = _as_float(lt.value_numeric)
        new = _as_float(data["value_numeric"])
        if cur is None or new is None or abs(cur - new) > 1e-6:
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

    lt.flag = compute_flag(
        _as_float(lt.value_numeric),
        _as_float(lt.reference_min),
        _as_float(lt.reference_max),
    )

    db.commit()
    db.refresh(lt)
    return LabTestOut.model_validate(lt)


@router.get("/codes", response_model=list[LabTestCodeSummary])
def list_lab_test_codes(
    patient_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
    else:
        patient = get_authorized_patient(patient_id, current_user, db, required_permission="read")

    rows = (
        db.query(LabTest, Document)
        .join(Document, LabTest.document_id == Document.id)
        .filter(
            LabTest.patient_id == patient.id,
            LabTest.confirmed_by_user.is_(True),
            Document.deleted_at.is_(None),
        )
        .all()
    )

    grouped: dict[str, list[tuple[date | None, LabTest, Document]]] = defaultdict(list)

    for lt, doc in rows:
        grouped[lt.test_code].append((_effective_date(lt, doc), lt, doc))

    summaries: list[LabTestCodeSummary] = []

    for code, items in grouped.items():
        items.sort(key=lambda x: _date_sort_key(x[0]))
        eff, lt, _doc = items[-1]

        summaries.append(
            LabTestCodeSummary(
                test_code=code,
                test_name_normalized=lt.test_name_normalized,
                last_value_numeric=lt.value_numeric,
                last_value_text=lt.value_text,
                last_unit=lt.unit,
                last_flag=lt.flag,
                last_date=eff,
                points_count=len(items),
            )
        )

    summaries.sort(key=lambda s: s.test_name_normalized.lower())
    return summaries


@router.get("/trend", response_model=TrendResponse)
def get_lab_test_trend(
    test_code: str = Query(...),
    patient_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if patient_id is None:
        _, patient = ensure_family_and_self_patient(db, current_user)
    else:
        patient = get_authorized_patient(patient_id, current_user, db, required_permission="read")

    rows = (
        db.query(LabTest, Document)
        .join(Document, LabTest.document_id == Document.id)
        .filter(
            LabTest.patient_id == patient.id,
            LabTest.test_code == test_code,
            LabTest.confirmed_by_user.is_(True),
            LabTest.value_numeric.isnot(None),
            Document.deleted_at.is_(None),
        )
        .all()
    )

    points: list[TrendPoint] = []

    for lt, doc in rows:
        eff = _effective_date(lt, doc)
        points.append(
            TrendPoint(
                date=eff,
                value_numeric=lt.value_numeric,
                value_text=lt.value_text,
                unit=lt.unit,
                reference_min=lt.reference_min,
                reference_max=lt.reference_max,
                flag=lt.flag,
                document_id=doc.id,
                document_title=doc.title,
                test_name_normalized=lt.test_name_normalized,
                confirmed_by_user=lt.confirmed_by_user,
                user_corrected=lt.user_corrected,
                created_at=lt.created_at,
            )
        )

    points.sort(key=lambda p: (_date_sort_key(p.date), p.created_at))

    test_name = points[-1].test_name_normalized if points else None
    unit = points[-1].unit if points else None

    return TrendResponse(
        patient_id=patient.id,
        test_code=test_code,
        test_name_normalized=test_name,
        unit=unit,
        points=points,
    )