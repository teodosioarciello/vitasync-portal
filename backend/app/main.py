import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, patients
from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.session import Base, engine
from app.services.storage import ensure_bucket, ensure_local_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creazione tabelle database in ambiente: %s", settings.environment)
    Base.metadata.create_all(bind=engine)

    try:
        if settings.storage_backend == "local":
            ensure_local_storage()
        else:
            ensure_bucket()
    except Exception as exc:
        logger.warning("Storage non disponibile all'avvio: %s", exc)

    yield

    logger.info("Arresto applicazione VitaSync Portal API.")


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

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "vitasync-api",
        "environment": settings.environment,
        "ai_enabled": settings.ai_enabled,
        "storage_backend": settings.storage_backend,
    }