"""
Sprint 6.3 - Estrazione valori esami di laboratorio con SLM LOCALE via Ollama.

L'AI "legge" il referto (testo estratto dal PDF oppure immagine del documento)
e restituisce SOLO i veri esami di laboratorio in JSON strutturato, scartando
indirizzi, footer, firme digitali e testo legale.

Privacy: la chiamata avviene sempre e solo verso un'istanza Ollama residente
sulla stessa macchina/rete locale (settings.ocr_ollama_base_url). Nessun dato
viene inviato a servizi internet esterni.

Se l'estrazione AI fallisce o restituisce risultati vuoti, il chiamante
(estraction.extract_from_document) usa il parser classico heuristico come
fallback, cosi' la review page non resta mai senza dati.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

LAB_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "ref_min": {"type": ["number", "null"]},
                    "ref_max": {"type": ["number", "null"]},
                    "flag": {
                        "type": ["string", "null"],
                        "enum": [None, "low", "high", "normal"],
                    },
                },
                "required": ["name", "value"],
            }
        }
    },
    "required": ["items"],
}

SYSTEM_PROMPT_IT = (
    "Sei un estrattore di dati da referti di laboratorio analisi italiani. "
    "Devi riconoscere SOLO gli esami di laboratorio (glucosio, colesterolo LDL/HDL, "
    "trigliceridi, creatinina, AST/ALT/GGT, emocromo, TSH, vitamina D, ecc.) "
    "con valore numerico, unita' di misura e intervallo di riferimento. "
    "NON sei un medico: non interpretare, non diagnosticare, non aggiungere esami "
    "che non compaiono nel documento. Non inventare valori."
)


def _build_user_prompt(text: str) -> str:
    return (
        "Estrai tutti gli esami di laboratorio presenti nel testo seguente.\n"
        "Regole:\n"
        "- 'name': nome dell'esame come compare nel referto;\n"
        "- 'value': valore numerico misurato (usa il punto come separatore decimale);\n"
        "- 'unit': unita' di misura (es. mg/dL), null se assente;\n"
        "- 'ref_min' e 'ref_max': limiti dell'intervallo di riferimento, null se assenti;\n"
        "- 'flag': 'low', 'high' o 'normal' in base al confronto col riferimento, null se incerto.\n\n"
        "IGNORA completamente: indirizzi, numeri di telefono, email, siti web, "
        "nomi di pazienti e medici, date, intestazioni di colonna, firme digitali, "
        "autorizzazioni ministeriali, riferimenti di legge, note e footer. "
        "Quegli elementi NON sono esami e non vanno mai restituiti.\n\n"
        f"TESTO DEL REFERTO:\n\"\"\"\n{text[:12000]}\n\"\"\""
    )


def _prompt_vision() -> str:
    return (
        "Questo e' un referto di laboratorio analisi italiano. Estrai TUTTI gli esami "
        "di laboratorio con nome, valore numerico, unita' di misura e intervallo di "
        "riferimento. IGNORA indirizzi, telefoni, nomi, date, firme, note legali e "
        "intestazioni: non sono esami. Restituisci solo i dati presenti nel documento, "
        "senza inventarne."
    )


def _ollama_chat_json(
    *,
    model: str,
    system: str,
    user: str,
    images_b64: list[str] | None = None,
    timeout: int | None = None,
) -> dict:
    """POST /api/chat su Ollama locale con response_format=json; ritorna il dict parsato."""
    base_url = settings.ocr_ollama_base_url.rstrip("/")
    message = {"role": "user", "content": user}
    if images_b64:
        message["images"] = images_b64

    payload = {
        "model": model,
        "stream": False,
        "format": LAB_JSON_SCHEMA,
        "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": system},
            message,
        ],
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            req, timeout=timeout or settings.ocr_ollama_timeout_seconds
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"Ollama AI-extract errore HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama non raggiungibile su {base_url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"Ollama AI-extract timeout dopo {timeout or settings.ocr_ollama_timeout_seconds}s"
        ) from exc

    raw = (body.get("message") or {}).get("content") or ""
    return _parse_json_object(raw)


def _parse_json_object(raw: str) -> dict:
    """Tollera wrapper ```json ... ``` e spazzatura attorno all'oggetto JSON."""
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end <= start:
        raise RuntimeError(f"Risposta AI non contiene JSON valido: {raw[:200]}")
    try:
        obj = json.loads(txt[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON AI malformato: {exc}; estratto={txt[start:end+1][:300]}") from exc
    if not isinstance(obj, dict):
        raise RuntimeError("La risposta AI non e' un oggetto JSON.")
    return obj


def _to_float(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    s = re.sub(r"[^0-9.\-+eE]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _clean_str(v, maxlen: int = 120) -> str | None:
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s[:maxlen] if s else None


def _sanitize_items(items: list) -> list[dict]:
    """Normalizza le righe restituite dal modello e scarta quelle non plausibili."""
    # riusa il filtro anti-righe-spazzatura del parser euristico (indirizzi,
    # footer, firme, riferimenti legali...) tenendo le due pipeline allineate.
    from app.services.extraction import _is_junk_line

    cleaned: list[dict] = []
    seen: set[tuple[str, float | None]] = set()

    for it in items:
        if not isinstance(it, dict):
            continue
        name = _clean_str(it.get("name"))
        if not name:
            continue
        # un vero nome esame non e' una frase intera ne' un recapito
        if len(name.split()) > 8:
            continue
        if re.search(r"(?i)(www\.|https?://|@[\w.-]+\.\w{2,}|\btel\b|\bfax\b)", name):
            continue
        try:
            if _is_junk_line(name):
                continue
        except Exception:
            pass

        value = _to_float(it.get("value"))
        if value is None:
            continue
        if abs(value) > 1_000_000:  # CAP, telefoni, anni: mai esami
            continue

        rmin = _to_float(it.get("ref_min"))
        rmax = _to_float(it.get("ref_max"))
        if rmin is not None and abs(rmin) > 1_000_000:
            rmin = None
        if rmax is not None and abs(rmax) > 1_000_000:
            rmax = None

        flag = _clean_str(it.get("flag"), 20)
        flag = flag.lower() if flag else None
        if flag not in {"low", "high", "normal"}:
            flag = None

        key = (name.lower(), value)
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(
            {
                "name": name,
                "value": value,
                "unit": _clean_str(it.get("unit"), 30),
                "ref_min": rmin,
                "ref_max": rmax,
                "flag": flag,
            }
        )

    return cleaned


def extract_lab_values_from_text(text: str, model: str | None = None) -> list[dict]:
    """
    Estrae gli esami di laboratorio da un testo di referto usando l'SLM locale.
    Ritorna una lista di dict puliti; solleva RuntimeError se l'AI fallisce.
    """
    if not text or len(text.strip()) < 40:
        raise RuntimeError("Testo troppo breve per l'estrazione AI.")

    chosen_model = model or settings.lab_extract_model or settings.ocr_ollama_model
    obj = _ollama_chat_json(
        model=chosen_model,
        system=SYSTEM_PROMPT_IT,
        user=_build_user_prompt(text),
    )
    items = obj.get("items")
    if not isinstance(items, list):
        raise RuntimeError("Risposta AI priva della lista 'items'.")

    cleaned = _sanitize_items(items)
    logger.info(
        "Estrazione AI lab completata: modello=%s, item grezzi=%d, tenuti=%d",
        chosen_model,
        len(items),
        len(cleaned),
    )
    return cleaned


def _encode_image(img: Image.Image) -> str:
    import base64

    max_dim = 1800
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize(
            (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    if img.mode != "RGB":
        img = img.convert("RGB")
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_lab_values_from_image(img: Image.Image, model: str | None = None) -> list[dict]:
    """
    Estrazione diretta dall'immagine (vision): il VLM locale legge il referto
    e restituisce gli esami in JSON, salta il passaggio OCR+tesseract.
    """
    chosen_model = model or settings.lab_extract_model or settings.ocr_ollama_model
    obj = _ollama_chat_json(
        model=chosen_model,
        system=SYSTEM_PROMPT_IT,
        user=_prompt_vision(),
        images_b64=[_encode_image(img)],
    )
    items = obj.get("items")
    if not isinstance(items, list):
        raise RuntimeError("Risposta vision AI priva della lista 'items'.")

    cleaned = _sanitize_items(items)
    logger.info(
        "Estrazione vision AI lab completata: modello=%s, item grezzi=%d, tenuti=%d",
        chosen_model,
        len(items),
        len(cleaned),
    )
    return cleaned
