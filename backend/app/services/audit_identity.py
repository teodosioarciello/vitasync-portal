from uuid import UUID

from fastapi import Request


def mark_audit_user(request: Request, user_id: UUID | str | None) -> None:
    """
    Salva in modo sicuro l'user_id nello request.state, cosi' il middleware
    audit puo' associare l'azione sensibile all'utente autenticato.

    Non fa mai fallire la richiesta: se il valore non e' valido, ignora.
    """
    if user_id is None:
        return

    try:
        if isinstance(user_id, UUID):
            value = user_id
        else:
            value = UUID(str(user_id))

        request.state.audit_user_id = value
    except Exception:
        return


def get_audit_user_id(request: Request) -> UUID | None:
    """
    Legge l'user_id eventualmente marcato nello request.state.
    Ritorna None se assente o non valido.
    """
    try:
        value = getattr(request.state, "audit_user_id", None)
    except Exception:
        return None

    if isinstance(value, UUID):
        return value

    if isinstance(value, str):
        try:
            return UUID(value)
        except Exception:
            return None

    return None