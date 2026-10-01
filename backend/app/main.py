import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    auth,
    documents,
    lab_tests,
    medicines,
    patients,
    reminders,
    therapies,
)
from app.core.config import settings
from app.db import audit_models  # noqa: F401  (registra AuditLog su Base.metadata)
from app.db import models  # noqa: F401
from app.db import therapy_models  # noqa: F401  (registra Medicine/Therapy/Reminder)
from app.db.session import Base, engine
from app.services.audit import derive_action, record_audit
from app.services.audit_identity import get_audit_user_id
from app.services.ratelimit import check_rate_limit
from app.services.storage import ensure_bucket, ensure_local_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_SECRET = "change-me-in-production"

RATE_LIMITS = {
    "/api/auth/login": {"limit": 10, "window": 300},
    "/api/auth/register": {"limit": 5, "window": 600},
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def _set_header_once(response, name: str, value: str) -> None:
    if name not in response.headers:
        response.headers[name] = value


def _apply_security_headers(response) -> None:
    for name, value in SECURITY_HEADERS.items():
        _set_header_once(response, name, value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.secret_key == DEFAULT_SECRET:
        if settings.environment == "production":
            raise RuntimeError(
                "SECRET_KEY ancora al default in environment=production. "
                "Imposta un segreto forte in .env prima di avviare in produzione."
            )
        logger.warning(
            "SECRET_KEY al default accettato solo in development. "
            "Cambia SECRET_KEY in .env prima di andare in produzione."
        )

    logger.info("Creazione tabelle database in ambiente: %s", settings.environment)
    Base.metadata.create_all(bind=engine)

    try:
        if settings.storage_backend == "local":
            ensure_local_storage()
        else:
            ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Storage non disponibile all'avvio: %s", exc)

    yield

    logger.info("Arresto applicazione VitaSync Portal API.")


from app.api import notifications
from app.api import reports
app = FastAPI(
    title="VitaSync Portal API",
    version="0.1.0",
    description="API iniziale per organizzazione personale/familiare di documenti sanitari.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# NB: l'ordine di dichiarazione NON e' dipenduto dal comportamento.
# Il rate limiter logga i propri 429 e ci applica gli header di sicurezza;
# il middleware audit salta i 429 per non doppiarli. Quindi ogni azione
# sensibile viene registrata esattamente una volta, bloccata o no.
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    _apply_security_headers(response)
    return response


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)

    if request.method == "OPTIONS":
        return response

    action = derive_action(request.method, request.url.path)
    if action is None:
        return response

    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        # gia' registrato dal rate limiter
        return response

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user_id = get_audit_user_id(request)

    record_audit(
        action=action,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        ip_address=client_ip,
        user_agent=user_agent,
        user_id=user_id,
    )
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    rule = RATE_LIMITS.get(request.url.path)
    if rule is None:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    key = "rl:{0}:{1}".format(request.url.path, client_ip)
    allowed, remaining, retry_after = check_rate_limit(
        key=key, limit=rule["limit"], window_seconds=rule["window"]
    )

    if not allowed:
        action = derive_action(request.method, request.url.path)
        record_audit(
            action=action,
            method=request.method,
            path=request.url.path,
            status_code=429,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            extra="rate_limited",
        )
        response = JSONResponse(
            status_code=429,
            content={"detail": "Troppe richieste. Riprova tra poco."},
        )
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(rule["limit"])
        response.headers["X-RateLimit-Remaining"] = "0"
        _apply_security_headers(response)
        return response

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(rule["limit"])
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(documents.router)
app.include_router(lab_tests.router)
app.include_router(medicines.router)
app.include_router(therapies.router)
app.include_router(reminders.router)
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "vitasync-api",
        "environment": settings.environment,
        "ai_enabled": settings.ai_enabled,
        "storage_backend": settings.storage_backend,
        "extraction": "pdf-local-v1",
        "hardening": "lite-v1",
        "therapy": "b1-v1",
        "audit": "identity-v1",
    }