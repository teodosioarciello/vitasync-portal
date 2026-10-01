"""
Sprint 3 - Report PDF per consulto medico.

Endpoint read-only che genera al volo un PDF riepilogativo dei valori
confermati da documenti attivi. Nulla viene salvato sul server.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db.models import Patient
from app.services import medical_report
from app.services.audit import record_audit
from app.services.family import ensure_family_and_self_patient

router = APIRouter()


@router.get("/medical-summary.pdf")
def medical_summary_pdf(
    patient_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _, self_patient = ensure_family_and_self_patient(db, current_user)

    if patient_id:
        try:
            pid = UUID(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="patient_id non valido.")

        patient = db.get(Patient, pid)
    else:
        patient = self_patient

    if patient is None:
        raise HTTPException(status_code=404, detail="Paziente non trovato.")

    if patient.family_id != self_patient.family_id:
        raise HTTPException(status_code=403, detail="Paziente non accessibile.")

    data = medical_report.collect_report_data(db, patient)
    pdf_bytes = medical_report.build_pdf_bytes(data)

    record_audit(
        action="report.medical_summary_download",
        method="GET",
        path="/api/reports/medical-summary.pdf",
        status_code=200,
        ip_address=None,
        user_agent=None,
        user_id=current_user.id,
        extra=(
            f"patient_id={patient.id};"
            f"groups={data['totals']['groups']};"
            f"rows={data['totals']['rows']}"
        ),
    )

    filename = (
        "vitasync-riepilogo-esami-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + ".pdf"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )