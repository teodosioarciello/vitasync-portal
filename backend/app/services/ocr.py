import logging
from pathlib import Path

import fitz
from PIL import Image, ImageOps
import pytesseract

from app.core.config import settings
from app.services import ocr_vlm

logger = logging.getLogger(__name__)

OCR_LANG_PRIMARY = "ita+eng"
OCR_LANG_FALLBACK = "eng"
OCR_CONFIG = "--oem 3 --psm 6"
PDF_OCR_DPI = 300
# Con backend VLM le pagine PDF possono essere ridimensionate dal client,
# quindi un DPI inferiore basta e accelera la rasterizzazione su CPU deboli.
PDF_OCR_DPI_VLM = 200

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


def _ocr_backend_name() -> str:
    backend = (settings.ocr_backend or "tesseract").strip().lower()
    if backend not in {"tesseract", "ollama", "hybrid"}:
        logger.warning("ocr_backend '%s' sconosciuto, uso 'tesseract'.", backend)
        return "tesseract"
    return backend


def _text_usable(text: str | None) -> bool:
    """Euristica: il testo VLM deve contenere almeno qualche cifra/parola."""
    if not text:
        return False
    stripped = text.strip()
    return len(stripped) >= 20 and any(ch.isdigit() or ch.isalpha() for ch in stripped)


def _image_to_text_auto(img: Image.Image) -> tuple[str, str]:
    """
    Dispatcher OCR in base a settings.ocr_backend:
      - tesseract: solo Tesseract (comportamento storico);
      - ollama:    solo VLM via Ollama, con fallback Tesseract se disabilitato/assente;
      - hybrid:    prova VLM prima, se fallisce o restituisce testo inusabile usa Tesseract.
    Ritorna (testo, sorgente_effettiva).
    """
    backend = _ocr_backend_name()

    if backend == "tesseract":
        return _image_to_text(img), "tesseract"

    vlm_error: str | None = None
    vlm_text: str | None = None
    try:
        vlm_text = ocr_vlm.transcribe_image(img)
    except Exception as exc:
        vlm_error = str(exc)
        logger.warning("OCR VLM fallito: %s", exc)

    if vlm_text and _text_usable(vlm_text):
        return vlm_text, f"vlm:{settings.ocr_ollama_model}"

    if backend == "ollama" and not settings.ocr_fallback_to_tesseract:
        raise RuntimeError(
            f"OCR VLM non riuscito e fallback Tesseract disabilitato: {vlm_error or 'risposta vuota'}"
        )

    logger.info("Uso fallback Tesseract (backend=%s, vlm_error=%s).", backend, vlm_error)
    return _image_to_text(img), "tesseract-fallback"


def ocr_image_path(path: Path) -> str:
    text, _source = ocr_image_detailed(path)
    return text


def ocr_image_detailed(path: Path) -> tuple[str, str]:
    """Come ocr_image_path, ma ritorna anche il motore effettivo usato."""
    with Image.open(path) as img:
        prepared = _prepare_image(img)
        text, source = _image_to_text_auto(prepared)
        logger.debug("OCR immagine %s completato con sorgente=%s", path.name, source)
        return text, source


def ocr_pdf_pages(path: Path) -> str:
    text, _source = ocr_pdf_pages_detailed(path)
    return text


def ocr_pdf_pages_detailed(path: Path) -> tuple[str, str]:
    """
    Come ocr_pdf_pages, ma ritorna anche un riepilogo dei motori usati
    (es. "vlm:qwen2.5vl:3b" oppure misto "vlm,tesseract-fallback").
    """
    doc = fitz.open(str(path))
    chunks: list[str] = []
    sources_used: set[str] = set()

    backend = _ocr_backend_name()
    dpi = PDF_OCR_DPI if backend == "tesseract" else PDF_OCR_DPI_VLM

    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text, source = _image_to_text_auto(img)
            chunks.append(text)
            sources_used.add(source.split(":")[0])
    finally:
        doc.close()

    return "\n".join(chunks), "+".join(sorted(sources_used)) or "none"


def extract_text_from_image(path: Path) -> str:
    return ocr_image_path(path)


def extract_text_from_pdf_with_ocr(path: Path) -> str:
    return ocr_pdf_pages(path)