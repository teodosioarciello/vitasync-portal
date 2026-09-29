import hashlib
import io
import logging
import uuid as uuid_lib
from datetime import date
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document

logger = logging.getLogger(__name__)

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

_minio_client = None


def get_minio_client():
    global _minio_client

    if _minio_client is None:
        from minio import Minio

        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    return _minio_client


def ensure_bucket() -> None:
    if settings.storage_backend != "minio":
        logger.info("Storage backend locale attivo: MinIO non inizializzato.")
        return

    try:
        client = get_minio_client()
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
            logger.info("Bucket MinIO creato: %s", settings.minio_bucket)
    except Exception as exc:
        logger.warning("Impossibile verificare/creare bucket MinIO: %s", exc)


def ensure_local_storage() -> None:
    LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info("Storage locale pronto in: %s", LOCAL_STORAGE_ROOT.resolve())


def _sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "document"

    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-")
    safe = safe.strip("._-") or "document"
    return safe[:120]


async def save_document(
    db: Session,
    patient_id,
    uploaded_by_user_id,
    title: str,
    document_type: str,
    file: UploadFile,
    document_date: date | None = None,
) -> Document:
    content_type = file.content_type or "application/octet-stream"

    if content_type not in settings.allowed_mime_set:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo di file non supportato.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    hasher = hashlib.sha256()
    buffer = io.BytesIO()
    size = 0

    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break

        size += len(chunk)

        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File troppo grande. Massimo consentito: {settings.max_upload_mb} MB.",
            )

        hasher.update(chunk)
        buffer.write(chunk)

    buffer.seek(0)

    safe_filename = _sanitize_filename(file.filename)
    relative_dir = Path("patients") / str(patient_id) / "documents" / str(uuid_lib.uuid4())

    if settings.storage_backend == "local":
        ensure_local_storage()

        dest_dir = LOCAL_STORAGE_ROOT / relative_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / safe_filename

        with dest_path.open("wb") as f:
            f.write(buffer.read())

        storage_key = (relative_dir / safe_filename).as_posix()

    else:
        storage_key = (
            f"patients/{patient_id}/documents/{uuid_lib.uuid4()}/{safe_filename}"
        )

        buffer.seek(0)

        client = get_minio_client()
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_key,
            data=buffer,
            length=size,
            content_type=content_type,
        )

    document = Document(
        patient_id=patient_id,
        uploaded_by_user_id=uploaded_by_user_id,
        title=title,
        document_type=document_type,
        source_filename=safe_filename,
        storage_key=storage_key,
        mime_type=content_type,
        size_bytes=size,
        sha256=hasher.hexdigest(),
        document_date=document_date,
        processing_status="pending",
        ai_status="disabled" if not settings.ai_enabled else "pending",
        metadata_json={},
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document
