import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email_stub(to: str, subject: str, body: str) -> None:
    """
    Stub email per sviluppo.
    In produzione sostituire con SMTP reale o provider email.
    """
    if settings.smtp_host:
        # TODO: implementare SMTP reale
        logger.info(
            "SMTP configurato ma non ancora implementato. Email simulata a=%s oggetto=%s",
            to,
            subject,
        )
    else:
        logger.info(
            "EMAIL STUB | to=%s | subject=%s | body=%s",
            to,
            subject,
            body,
        )


def send_verification_email(to: str, verification_url: str) -> None:
    subject = "VitaSync Portal - Verifica email"
    body = f"Per verificare il tuo account, apri questo link: {verification_url}"
    send_email_stub(to, subject, body)


def send_password_reset_email(to: str, reset_url: str) -> None:
    subject = "VitaSync Portal - Reset password"
    body = f"Per reimpostare la password, apri questo link: {reset_url}"
    send_email_stub(to, subject, body)