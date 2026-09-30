import os
from typing import BinaryIO

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_HEADER_BYTES = 16

_PDF_HEADER = b"%PDF"
_JPEG_HEADER = b"\xff\xd8\xff"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _detect_mime(header: bytes) -> str:
    if header.startswith(_PDF_HEADER):
        return "application/pdf"

    if header.startswith(_JPEG_HEADER):
        return "image/jpeg"

    if header.startswith(_PNG_HEADER):
        return "image/png"

    raise HTTPException(
        status_code=415,
        detail="Tipo file non supportato. Sono accettati solo PDF, JPEG e PNG validi.",
    )


def validate_upload_stream(
    stream: BinaryIO,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    """
    Valida un file binario in base a:
    - dimensione massima;
    - non vuoto;
    - magic byte PDF/JPEG/PNG.

    Ritorna il MIME tipo rilevato dai magic byte.
    Non consuma il stream: alla fine posiziona il puntatore a 0.
    """
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="File non leggibile.",
        ) from exc

    stream.seek(0)

    if size <= 0:
        raise HTTPException(
            status_code=400,
            detail="File vuoto.",
        )

    if size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File troppo grande. Limite massimo: {max_mb} MB.",
        )

    header = stream.read(MIN_HEADER_BYTES)
    stream.seek(0)

    if not header:
        raise HTTPException(
            status_code=400,
            detail="File vuoto.",
        )

    return _detect_mime(header)


def validate_upload_file(
    file: UploadFile,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    stream = getattr(file, "file", None)

    if stream is None:
        raise HTTPException(
            status_code=400,
            detail="File non valido.",
        )

    return validate_upload_stream(
        stream,
        filename=file.filename,
        content_type=file.content_type,
        max_bytes=max_bytes,
    )