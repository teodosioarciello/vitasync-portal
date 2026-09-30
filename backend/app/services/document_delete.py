import logging
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, LabTest
from app.db.therapy_models import Therapy

logger = logging.getLogger(__name__)

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)


def _resolve_document_path(document: Document) -> Path | None:
    """
    Risolve il percorso fisico del documento in modo sicuro.
    Evita path traversal tramite storage_key manipolato.
    """
    if not document.storage_key:
        return None

    root = LOCAL_STORAGE_ROOT.resolve()

    try:
        target = (root / document.storage_key).resolve()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Percorso documento non valido.",
        ) from exc

    if not target.is_relative_to(root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Percorso documento non valido.",
        )

    return target


def delete_document_and_file(db: Session, document: Document) -> bool:
    """
    Elimina documento, lab_tests collegate, detach terapie e file fisico.
    Ritorna True se il file esisteva ed e' stato eliminato, False se era gia' assente.
    """
    path = _resolve_document_path(document)
    file_existed = False

    if path is not None:
        if path.exists():
            if not path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Percorso documento non e' un file valido.",
                )

            try:
                path.unlink()
                file_existed = True
                logger.info("File documento eliminato: %s", path)
            except PermissionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Impossibile eliminare il file: permessi insufficienti.",
                ) from exc
            except OSError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Impossibile eliminare il file: {exc}",
                ) from exc
        else:
            logger.info("File documento gia' assente: %s", path)

    try:
        db.query(LabTest).filter(
            LabTest.document_id == document.id
        ).delete(synchronize_session=False)

        db.query(Therapy).filter(
            Therapy.prescription_document_id == document.id
        ).update(
            {Therapy.prescription_document_id: None},
            synchronize_session=False,
        )

        db.delete(document)
        db.commit()
    except Exception as exc:
        db.rollback()

        if file_existed:
            logger.critical(
                "File documento %s eliminato ma transazione DB fallita: %s",
                document.id,
                exc,
            )

        raise

    return file_existed