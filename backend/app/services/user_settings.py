"""
Sprint B Step 4E.

Servizio per gestire le preferenze notifiche dell'utente.

Regole:
- se l'utente ha una riga user_settings, quelle impostazioni vincono;
- altrimenti si applicano i default (console + env var globali).
- la password SMTP e' salvata in chiaro: dichiarato in docs.
"""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import User
from app.db.settings_models import UserSettings

logger = logging.getLogger(__name__)

CHANNEL_CONSOLE = "console"
CHANNEL_SMTP = "smtp"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_or_create_settings(db: Session, user: User) -> UserSettings:
    """
    Ritorna le UserSettings dell'utente, creandole con default se assenti.
    """
    settings = db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def settings_to_dict(settings: UserSettings, *, include_password: bool = False) -> dict:
    """
    Serializza le impostazioni per l'API.
    La password SMTP non viene mai esposta di default.
    """
    data = {
        "user_id": str(settings.user_id),
        "notification_channel": settings.notification_channel,
        "notifications_enabled": settings.notifications_enabled,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user,
        "smtp_from": settings.smtp_from,
        "smtp_use_tls": settings.smtp_use_tls,
        "has_smtp_password": bool(settings.smtp_password),
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }

    if include_password:
        data["smtp_password"] = settings.smtp_password

    return data


def update_settings(db: Session, user: User, payload: dict) -> UserSettings:
    """
    Aggiorna le UserSettings dell'utente.

    Campi accettati:
    - notification_channel: 'console' | 'smtp'
    - notifications_enabled: bool
    - smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_use_tls
    """
    settings = get_or_create_settings(db, user)

    allowed = {
        "notification_channel",
        "notifications_enabled",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        "smtp_use_tls",
    }

    for key, value in payload.items():
        if key not in allowed:
            continue

        if key == "notification_channel" and value not in (CHANNEL_CONSOLE, CHANNEL_SMTP):
            raise ValueError("notification_channel deve essere 'console' o 'smtp'.")

        if key == "smtp_password" and value == "":
            # stringa vuota => cancella password esistente
            settings.smtp_password = None
            continue

        if value == "":
            # stringa vuota per campi SMTP opzionali => NULL
            setattr(settings, key, None)
        else:
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


def resolve_effective_smtp(db: Session, user: User) -> dict:
    """
    Ritorna la configurazione SMTP effettiva da usare per l'invio:
    - se l'utente ha impostato smtp_host, usa quella;
    - altrimenti usa le env var globali (retrocompatibilita').
    """
    settings = get_or_create_settings(db, user)

    host = settings.smtp_host or os.getenv("SMTP_HOST")
    port = settings.smtp_port
    if port is None:
        raw_port = os.getenv("SMTP_PORT", "587")
        try:
            port = int(raw_port)
        except ValueError:
            port = 587

    user_smtp = settings.smtp_user or os.getenv("SMTP_USER")
    password = settings.smtp_password or os.getenv("SMTP_PASSWORD")
    sender = settings.smtp_from or os.getenv("SMTP_FROM") or user_smtp or "noreply@vitasync.local"

    use_tls = settings.smtp_use_tls if settings.smtp_host else _env_bool("SMTP_STARTTLS", not _env_bool("SMTP_SSL", False))

    return {
        "host": host,
        "port": port,
        "user": user_smtp,
        "password": password,
        "sender": sender,
        "use_tls": use_tls,
    }