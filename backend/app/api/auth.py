from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    EmailVerificationToken,
    PasswordResetToken,
    Session as SessionModel,
    User,
)
from app.deps import get_current_user, get_db
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    UserOut,
)
from app.services.audit_identity import mark_audit_user
from app.services.email import send_password_reset_email, send_verification_email
from app.services.family import ensure_family_and_self_patient
from app.services.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _create_session(db: Session, user: User, request: Request) -> str:
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)

    session = SessionModel(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()

    return raw_token


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_expire_days * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if settings.registration_mode == "closed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registrazione al momento non disponibile.",
        )

    if settings.require_invite_code:
        if not settings.invite_code or payload.invite_code != settings.invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Codice invito mancante o non valido.",
            )

    if not payload.accept_privacy or not payload.accept_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Per registrarti devi accettare informativa privacy e termini.",
        )

    existing_user = (
        db.query(User)
        .filter(or_(User.username == payload.username, User.email == payload.email))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username o email gia registrati.",
        )

    now = datetime.now(timezone.utc)

    auto_verify = settings.dev_auto_verify_email or not settings.email_verification_required

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        birth_date=payload.birth_date,
        is_active=True,
        email_verified=auto_verify,
        accepted_privacy_at=now if payload.accept_privacy else None,
        accepted_terms_at=now if payload.accept_terms else None,
    )

    db.add(user)
    db.flush()

    verification_url = None

    if settings.email_verification_required and not user.email_verified:
        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        expires_at = now + timedelta(hours=24)

        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

        verification_url = (
            str(request.base_url).rstrip("/")
            + f"/api/auth/verify-email?token={raw_token}"
        )

        send_verification_email(user.email, verification_url)

    db.commit()
    db.refresh(user)

    mark_audit_user(request, user.id)

    return RegisterResponse(
        user=UserOut.model_validate(user),
        verification_required=settings.email_verification_required and not user.email_verified,
        verification_url=verification_url if settings.dev_expose_verification_link else None,
        message=(
            "Account creato. Controlla la email per verificare l'account."
            if settings.email_verification_required and not user.email_verified
            else "Account creato e pronto per il login."
        ),
    )


@router.get("/verify-email", response_model=MessageResponse)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)

    verification_token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        .first()
    )

    if not verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token di verifica non valido o scaduto.",
        )

    user = db.get(User, verification_token.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non trovato.",
        )

    user.email_verified = True
    verification_token.used_at = now

    db.commit()

    return MessageResponse(
        detail="Email verificata con successo. Ora puoi effettuare il login."
    )


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    identifier = payload.identifier.strip().lower()

    user = (
        db.query(User)
        .filter(or_(User.username == identifier, User.email == identifier))
        .first()
    )

    if not user or not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account non attivo.",
        )

    if settings.email_verification_required and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verifica prima la tua email.",
        )

    raw_token = _create_session(db, user, request)
    _set_session_cookie(response, raw_token)

    mark_audit_user(request, user.id)

    ensure_family_and_self_patient(db, user)

    return UserOut.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(settings.session_cookie_name)

    if token:
        token_hash = hash_token(token)
        session = (
            db.query(SessionModel)
            .filter(SessionModel.token_hash == token_hash)
            .first()
        )
        if session:
            mark_audit_user(request, session.user_id)
            db.delete(session)
            db.commit()

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )

    return MessageResponse(detail="Logout effettuato.")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/password-reset/request", response_model=MessageResponse)
def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()

    if user and user.is_active:
        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        db.commit()

        reset_url = (
            str(request.base_url).rstrip("/")
            + f"/api/auth/password-reset/confirm?token={raw_token}"
        )
        send_password_reset_email(user.email, reset_url)

    return MessageResponse(
        detail="Se l'email e registrata, riceverai un link per reimpostare la password."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def password_reset_confirm(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    token_hash = hash_token(payload.token)
    now = datetime.now(timezone.utc)

    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token di reset non valido o scaduto.",
        )

    user = db.get(User, reset_token.user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non valido.",
        )

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = now

    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()

    db.commit()

    return MessageResponse(detail="Password reimpostata con successo.")