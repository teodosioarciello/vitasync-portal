import logging
from uuid import UUID

from app.db.audit_models import AuditLog
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

AUDIT_VERSION = "identity-v1"


def derive_action(method: str, path: str) -> str | None:
    """
    Mappa method+path -> azione sensibile. Ritorna None per le letture (GET)
    e per tutto cio' che non vogliamo tracciare, per non riempire la tabella.
    """
    if method == "GET":
        return None

    if path.startswith("/api/auth/login"):
        return "auth.login"
    if path.startswith("/api/auth/register"):
        return "auth.register"
    if path.startswith("/api/auth/logout"):
        return "auth.logout"

    if path.startswith("/api/documents"):
        if method == "POST" and path.endswith("/restore"):
            return "document.restore"

        if method == "DELETE" and path.endswith("/permanent"):
            return "document.permanent_delete"

        if path.startswith("/api/documents/upload"):
            return "document.upload"

        if "/extract" in path:
            return "document.extract"

        if "/confirm-all" in path:
            return "lab_test.confirm_all"

        if method == "DELETE":
            return "document.soft_delete"

    if path.startswith("/api/lab-tests") and method == "PATCH":
        return "lab_test.update"

    if path.startswith("/api/medicines"):
        if method == "POST":
            return "medicine.create"
        if method == "PATCH":
            return "medicine.update"
        if method == "DELETE":
            return "medicine.delete"

    if path.startswith("/api/therapies"):
        if method == "POST":
            return "therapy.create"
        if method == "PATCH":
            return "therapy.update"

    if path.startswith("/api/reminders"):
        if method == "POST":
            return "reminder.create"
        if method == "PATCH":
            return "reminder.update"

    return None


def _coerce_user_id(user_id) -> UUID | None:
    if user_id is None:
        return None

    if isinstance(user_id, UUID):
        return user_id

    try:
        return UUID(str(user_id))
    except Exception:
        return None


def record_audit(
    action: str | None,
    method: str,
    path: str,
    status_code: int | None,
    ip_address: str | None,
    user_agent: str | None,
    user_id=None,
    extra: str | None = None,
) -> None:
    """
    Scrive una riga di audit. Non fa MAI fallire la richiesta: ogni errore
    viene inghiottito e loggato. Apre/chiude la propria sessione DB.

    NB: sync dentro contesto async - accettabile in dev; in prod valutare
    threadpool/queue.
    """
    db = None
    try:
        db = SessionLocal()
        row = AuditLog(
            action=action,
            method=method,
            path=(path[:512] if path else None),
            status_code=status_code,
            ip_address=ip_address,
            user_agent=(user_agent[:512] if user_agent else None),
            user_id=_coerce_user_id(user_id),
            extra=extra,
        )
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit log non registrato (%s): %s", action, exc)
        if db is not None:
            db.rollback()
    finally:
        if db is not None:
            db.close()