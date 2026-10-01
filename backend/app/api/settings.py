"""
Sprint B Step 4E.

Endpoint per leggere/aggiornare le preferenze notifiche dell'utente
e per inviare una email di prova.
"""

import logging
import smtplib
from email.message import EmailMessage
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db.models import User
from app.services import user_settings
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingsRead(BaseModel):
    user_id: str
    notification_channel: str
    notifications_enabled: bool
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    has_smtp_password: bool = False
    updated_at: str | None = None


class SettingsUpdate(BaseModel):
    notification_channel: str | None = Field(None, pattern="^(console|smtp)$")
    notifications_enabled: bool | None = None
    smtp_host: str | None = Field(None, max_length=255)
    smtp_port: int | None = Field(None, ge=1, le=65535)
    smtp_user: str | None = Field(None, max_length=255)
    smtp_password: str | None = Field(None, max_length=255)
    smtp_from: str | None = Field(None, max_length=255)
    smtp_use_tls: bool | None = None


class TestEmailResponse(BaseModel):
    ok: bool
    message: str
    recipient: str


@router.get("", response_model=SettingsRead)
def get_my_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = user_settings.get_or_create_settings(db, current_user)
    return user_settings.settings_to_dict(settings, include_password=False)


@router.patch("", response_model=SettingsRead)
def patch_my_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = payload.model_dump(exclude_unset=True)
        settings = user_settings.update_settings(db, current_user, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    record_audit(
        action="settings.update",
        method="PATCH",
        path="/api/settings",
        status_code=200,
        ip_address=None,
        user_agent=None,
        user_id=current_user.id,
        extra=f"channel={settings.notification_channel};enabled={settings.notifications_enabled}",
    )

    return user_settings.settings_to_dict(settings, include_password=False)


@router.post("/test-email", response_model=TestEmailResponse)
def test_email(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invia una email di prova all'utente stesso.
    Utile per verificare la configurazione SMTP prima di abilitare il canale.
    """
    settings = user_settings.get_or_create_settings(db, current_user)
    recipient = current_user.email

    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="Il tuo profilo non ha un indirizzo email. Impossibile inviare il test.",
        )

    smtp_cfg = user_settings.resolve_effective_smtp(db, current_user)

    if not smtp_cfg["host"]:
        record_audit(
            action="settings.test_email",
            method="POST",
            path="/api/settings/test-email",
            status_code=400,
            ip_address=None,
            user_agent=None,
            user_id=current_user.id,
            extra="reason=smtp_host_missing",
        )
        raise HTTPException(
            status_code=400,
            detail="SMTP host non configurato ne' per l'utente ne' a livello globale.",
        )

    msg = EmailMessage()
    msg["From"] = smtp_cfg["sender"]
    msg["To"] = recipient
    msg["Subject"] = "VitaSync Portal - email di prova"
    msg.set_content(
        "Questa e' una email di prova generata da VitaSync Portal.\n\n"
        "Se hai ricevuto questo messaggio, la configurazione SMTP funziona correttamente.\n"
    )

    try:
        if smtp_cfg["use_tls"]:
            server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=30)

        try:
            if smtp_cfg["user"]:
                server.login(smtp_cfg["user"], smtp_cfg["password"] or "")
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except Exception as exc:
        record_audit(
            action="settings.test_email",
            method="POST",
            path="/api/settings/test-email",
            status_code=502,
            ip_address=None,
            user_agent=None,
            user_id=current_user.id,
            extra=f"error={type(exc).__name__}:{str(exc)[:200]}",
        )
        raise HTTPException(status_code=502, detail=f"Invio email fallito: {exc}")

    record_audit(
        action="settings.test_email",
        method="POST",
        path="/api/settings/test-email",
        status_code=200,
        ip_address=None,
        user_agent=None,
        user_id=current_user.id,
        extra=f"recipient={recipient}",
    )

    return TestEmailResponse(
        ok=True,
        message="Email di prova inviata.",
        recipient=recipient,
    )