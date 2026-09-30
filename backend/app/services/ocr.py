import logging
from pathlib import Path

import fitz
from PIL import Image, ImageOps
import pytesseract

logger = logging.getLogger(__name__)

OCR_LANG_PRIMARY = "ita+eng"
OCR_LANG_FALLBACK = "eng"
OCR_CONFIG = "--oem 3 --psm 6"
PDF_OCR_DPI = 300

SUPPORTED_IMAGE_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
}


def is_supported_image_mime(mime_type: str | None) -> bool:
    return (mime_type or "").lower() in SUPPORTED_IMAGE_MIMES


def _prepare_image(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)

    if img.mode in {"RGBA", "LA", "P"}:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    max_dim = max(img.size)
    if max_dim < 1000:
        scale = 2
        img = img.resize(
            (img.width * scale, img.height * scale),
            Image.Resampling.LANCZOS,
        )

    return img


def _image_to_text(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(
            img,
            lang=OCR_LANG_PRIMARY,
            config=OCR_CONFIG,
        )
    except Exception as primary_exc:
        logger.warning(
            "OCR con lingua %s non disponibile o fallito: %s. Tentativo fallback %s.",
            OCR_LANG_PRIMARY,
            primary_exc,
            OCR_LANG_FALLBACK,
        )
        try:
            return pytesseract.image_to_string(
                img,
                lang=OCR_LANG_FALLBACK,
                config=OCR_CONFIG,
            )
        except Exception as exc:
            raise RuntimeError(f"Tesseract OCR non disponibile o fallito: {exc}") from exc


def ocr_image_path(path: Path) -> str:
    with Image.open(path) as img:
        prepared = _prepare_image(img)
        return _image_to_text(prepared)


def ocr_pdf_pages(path: Path) -> str:
    doc = fitz.open(str(path))
    chunks: list[str] = []

    try:
        for page in doc:
            pix = page.get_pixmap(dpi=PDF_OCR_DPI)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            chunks.append(_image_to_text(img))
    finally:
        doc.close()

    return "\n".join(chunks)


def extract_text_from_image(path: Path) -> str:
    return ocr_image_path(path)


def extract_text_from_pdf_with_ocr(path: Path) -> str:
    return ocr_pdf_pages(path)