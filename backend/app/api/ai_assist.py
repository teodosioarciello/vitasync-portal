"""
Sprint 6.1 - API AI esterna opzionale.
GET  /api/ai-assist/status
POST /api/ai-assist/analyze?patient_id=...
Regole:
- endpoint disabilitato di default;
- invia solo export pseudonimizzato;
- ultima guardia privacy prima della chiamata esterna;
- non salva la risposta nei dati confermati.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.health_summary import _collect_data, _get_patient
from app.core.config import settings
from app.db.models import User
from app.db.weight_models import WeightMeasurement
from app.deps import get_current_user, get_db
from app.services.ai_external import (
    AI_DISCLAIMER_IT,
    ALLOWED_PROVIDERS,
    SYSTEM_PROMPT_IT,
    assert_no_identifiers,
    build_ai_user_prompt,
    call_external_ai,
)
from app.services.health_alerts import build_health_summary
from app.services.health_export import build_markdown_export
from app.services.therapy_test_context import find_therapy_context_for_test

router = APIRouter(prefix="/api/ai-assist", tags=["ai-assist"])


class AiStatusOut(BaseModel):
    enabled: bool
    provider: str
    model: str
    allowed_providers: list[str]
    data_scope: str
    stored: bool
    disclaimer: str


class AiAnalyzeOut(BaseModel):
    answer: str
    provider: str
    model: str
    generated_at: str
    disclaimer: str
    data_scope: str
    stored: bool


def _base_url_for_provider(provider: str) -> str | None:
    if provider == "openai":
        return settings.ai_openai_base_url
    if provider == "anthropic":
        return settings.ai_anthropic_base_url
    if provider == "ollama":
        return settings.ai_ollama_base_url
    return None


@router.get("/status", response_model=AiStatusOut)
def get_ai_status(
    current_user: User = Depends(get_current_user),
):
    return AiStatusOut(
        enabled=bool(settings.ai_external_enabled),
        provider=str(settings.ai_provider or ""),
        model=str(settings.ai_model or ""),
        allowed_providers=sorted(ALLOWED_PROVIDERS),
        data_scope="pseudonimizzato",
        stored=False,
        disclaimer=AI_DISCLAIMER_IT,
    )


@router.post("/analyze", response_model=AiAnalyzeOut)
def analyze_with_external_ai(
    patient_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.ai_external_enabled:
        raise HTTPException(
            status_code=403,
            detail="AI esterna disabilitata. Imposta AI_EXTERNAL_ENABLED=true e configura un provider.",
        )

    provider = str(settings.ai_provider or "").lower().strip()
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail="Provider AI non configurato o non consentito.",
        )

    patient = _get_patient(patient_id, current_user, db)
    d = _collect_data(patient, db)

    weights_rows = (
        db.query(WeightMeasurement)
        .filter(WeightMeasurement.patient_id == patient_id)
        .order_by(WeightMeasurement.measured_at.desc())
        .limit(50)
        .all()
    )
    weights = [
        {"weight_kg": float(w.weight_kg), "measured_at": w.measured_at}
        for w in weights_rows
    ]

    summary = build_health_summary(
        patient=d["patient"],
        confirmed_labs=d["confirmed_labs"],
        latest_document_date=d["latest_document_date"],
        bmi_result=d["bmi_result"],
        active_medicines=d["active_medicines"],
        therapy_context_fn=find_therapy_context_for_test,
    )

    markdown = build_markdown_export(
        patient=d["patient"],
        confirmed_labs=d["confirmed_labs"],
        therapies=d["active_therapies"],
        weights=weights,
        bmi_result=d["bmi_result"],
        summary=summary,
        anonymize=True,
        generated_at=datetime.now(timezone.utc),
    )

    forbidden = [
        d["patient"].get("display_name"),
        getattr(current_user, "email", None),
        getattr(current_user, "username", None),
    ]

    try:
        assert_no_identifiers(markdown, forbidden, "export pseudonimizzato")
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Blocco privacy: l'export pseudonimizzato contiene ancora un identificatore reale.",
        )

    user_prompt = build_ai_user_prompt(markdown)

    try:
        result = call_external_ai(
            provider=provider,
            model=str(settings.ai_model or ""),
            api_key=settings.ai_api_key,
            base_url=_base_url_for_provider(provider),
            system_prompt=SYSTEM_PROMPT_IT,
            user_prompt=user_prompt,
            timeout=int(settings.ai_timeout_seconds or 30),
            max_prompt_chars=int(settings.ai_max_prompt_chars or 12000),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Configurazione AI non valida: {exc}")
    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Provider AI non raggiungibile o risposta non valida.",
        )

    return AiAnalyzeOut(**result)