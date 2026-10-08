"""
Sprint OCR - Client VLM via Ollama per riconoscimento testo (OCR "intelligente").

Progettato per girare su hardware modesto (es. Raspberry Pi 5, solo CPU):
- nessun pacchetto extra richiesto: usa urllib dalla stdlib;
- invia l'immagine in base64 all'endpoint /api/generate di Ollama locale;
- modello consigliato: qwen2.5vl:3b (~4 GB RAM), alternative: minicpm-v, gemma3.

I dati non lasciano mai la macchina: Ollama gira in locale.
"""
import base64
import json
import logging
from io import BytesIO

import urllib.error
import urllib.request

from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

OCR_VLM_PROMPT_IT = (
    "Eseguimi l'OCR completo di questa immagine. Restituisci SOLO il testo "
    "trascritto riga per riga, fedelmente, mantenendo numeri, unita' di misura "
    "e intervalli di riferimento. Non aggiungere commenti, titoli inventati o "
    "spiegazioni. Se una parte e' illeggibile, trascrivi il meglio possibile."
)

# Limite difensivo lato payload: ridimensiona oltre questa dimensione massima
# per non mandare immagini enormi al modello (contesto/ram su RPi5).
MAX_IMAGE_DIMENSION = 1800


def _encode_image(img: Image.Image) -> str:
    if max(img.size) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(img.size)
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    if img.mode != "RGB":
        img = img.convert("RGB")

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def ollama_is_available(base_url: str | None = None, timeout: int = 5) -> bool:
    """Ping economico dell'endpoint /api/tags di Ollama."""
    url = f"{(base_url or settings.ocr_ollama_base_url).rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def transcribe_image(img: Image.Image, model: str | None = None) -> str:
    """
    Trascrive un'immagine tramite un modello vision-language su Ollama locale.
    Solleva RuntimeError se il servizio non e' raggiungibile o fallisce.
    """
    base_url = settings.ocr_ollama_base_url.rstrip("/")
    chosen_model = model or settings.ocr_ollama_model

    payload = {
        "model": chosen_model,
        "prompt": OCR_VLM_PROMPT_IT,
        "images": [_encode_image(img)],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 4096,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=settings.ocr_ollama_timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"Ollama OCR errore HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama OCR non raggiungibile su {base_url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"Ollama OCR timeout dopo {settings.ocr_ollama_timeout_seconds}s "
            f"(modello {chosen_model} su CPU puo' essere lento)."
        ) from exc

    text = (body.get("response") or "").strip()
    if not text:
        raise RuntimeError(f"Ollama OCR ha restituito risposta vuota (modello {chosen_model}).")

    logger.info("OCR VLM completato: modello=%s, caratteri=%d", chosen_model, len(text))
    return text
