import logging
import re
from pathlib import Path

import fitz
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, LabTest
from app.services.ocr import (
    extract_text_from_image,
    extract_text_from_pdf_with_ocr,
    is_supported_image_mime,
)

logger = logging.getLogger(__name__)

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

STATUS_WORDS = {
    "negativo",
    "positivo",
    "reattivo",
    "non reattivo",
    "assente",
    "presente",
    "normale",
    "alterato",
}

UNIT_HINTS = {
    "mg/dl",
    "mg/l",
    "mmol/l",
    "umol/l",
    "g/l",
    "g/dl",
    "u/l",
    "miu/l",
    "uiu/ml",
    "ng/ml",
    "pg/ml",
    "ug/l",
    "ml/min",
    "ml/min/1.73",
    "10^3/ul",
    "10*3/ul",
    "k/ul",
    "mcm",
    "fl",
    "pg",
    "%",
    "g",
    "mg",
    "meq/l",
    "mmhg",
}

EXAM_SYNONYMS = {
    "GLUCOSIO": ("glucose", "Glucosio"),
    "GLICEMIA": ("glucose", "Glucosio"),
    "GOT AST": ("ast", "AST (GOT)"),
    "AST": ("ast", "AST (GOT)"),
    "GPT ALT": ("alt", "ALT (GPT)"),
    "ALT": ("alt", "ALT (GPT)"),
    "GGT": ("ggt", "GGT"),
    "FOSFATASI ALCALINE": ("alp", "Fosfatasi alcalina"),
    "BILIRUBINA TOTALE": ("bilirubin_total", "Bilirubina totale"),
    "BILIRUBINA DIRETTA": ("bilirubin_direct", "Bilirubina diretta"),
    "CREATININA": ("creatinine", "Creatinina"),
    "EGFR": ("egfr", "eGFR"),
    "FILTRO GLOMERULARE": ("egfr", "eGFR"),
    "UREA": ("urea", "Urea"),
    "AZOTEMIA": ("urea", "Urea"),
    "ACIDO URICO": ("uric_acid", "Acido urico"),
    "LIPASI": ("lipase", "Lipasi"),
    "AMILASI": ("amylase", "Amilasi"),
    "COLESTEROLO TOTALE": ("cholesterol_total", "Colesterolo totale"),
    "COLESTEROLO LDL": ("ldl", "Colesterolo LDL"),
    "LDL": ("ldl", "Colesterolo LDL"),
    "COLESTEROLO HDL": ("hdl", "Colesterolo HDL"),
    "HDL": ("hdl", "Colesterolo HDL"),
    "TRIGLICERIDI": ("triglycerides", "Trigliceridi"),
    "HBA1C": ("hba1c", "Emoglobina glicata"),
    "HBALC": ("hba1c", "Emoglobina glicata"),
    "EMOGLOBINA GLICATA": ("hba1c", "Emoglobina glicata"),
    "EMOGLOBINA": ("hemoglobin", "Emoglobina"),
    "HB": ("hemoglobin", "Emoglobina"),
    "LEUCOCITI": ("wbc", "Leucociti"),
    "GB": ("wbc", "Leucociti"),
    "PIASTRINE": ("platelets", "Piastrine"),
    "PLT": ("platelets", "Piastrine"),
    "VES": ("ves", "VES"),
    "PCR": ("pcr", "PCR"),
    "PROTEINA C REATTIVA": ("pcr", "PCR"),
    "TSH": ("tsh", "TSH"),
    "FT4": ("ft4", "FT4"),
    "FT3": ("ft3", "FT3"),
    "SODIO": ("sodium", "Sodio"),
    "POTASSIO": ("potassium", "Potassio"),
    "CLORO": ("chloride", "Cloro"),
    "CALCIO": ("calcium", "Calcio"),
    "FERRITINA": ("ferritin", "Ferritina"),
    "FERRO": ("iron", "Ferro"),
    "VITAMINA D": ("vitamin_d", "Vitamina D"),
}

_VALUE_RE = re.compile(r"^[-+]?\d+(?:[.,]\d+)?$")
_RANGE_DASH_RE = re.compile(
    r"^([-+]?\d+(?:[.,]\d+)?)\s*[-–]\s*([-+]?\d+(?:[.,]\d+)?)$"
)
_RANGE_LT_RE = re.compile(r"^[<≤]\s*([-+]?\d+(?:[.,]\d+)?)$")
_RANGE_GT_RE = re.compile(r"^[>≥]\s*([-+]?\d+(?:[.,]\d+)?)$")


def _normalize_key(raw: str) -> str:
    s = raw.upper()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _slug(raw: str) -> str:
    s = raw.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "exam"


def _title(raw: str) -> str:
    return " ".join(w.capitalize() for w in raw.split())


def normalize_exam_name(raw: str) -> tuple[str, str, float]:
    key = _normalize_key(raw)
    if key in EXAM_SYNONYMS:
        code, display = EXAM_SYNONYMS[key]
        return code, display, 0.9
    return _slug(raw), _title(raw), 0.5


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def is_value_token(token: str) -> bool:
    t = token.lower().strip("%")
    if t in STATUS_WORDS:
        return True
    return bool(_VALUE_RE.match(token))


def parse_value(value_raw: str) -> tuple[float | None, str | None]:
    v = value_raw.strip()
    pct = v.endswith("%")
    core = v.rstrip("%").strip()
    num = _to_float(core)
    if num is not None:
        return num, None
    return None, v.lower() if pct is False else v


def parse_reference(range_str: str) -> tuple[float | None, float | None, str | None]:
    rs = (range_str or "").strip()
    if not rs:
        return None, None, None

    m = _RANGE_DASH_RE.match(rs)
    if m:
        return _to_float(m.group(1)), _to_float(m.group(2)), rs

    m = _RANGE_LT_RE.match(rs)
    if m:
        return None, _to_float(m.group(1)), rs

    m = _RANGE_GT_RE.match(rs)
    if m:
        return _to_float(m.group(1)), None, rs

    return None, None, rs


def compute_flag(
    value_num: float | None,
    rmin: float | None,
    rmax: float | None,
) -> str | None:
    if value_num is None:
        return "unknown"
    if rmin is not None and value_num < rmin:
        return "below_range"
    if rmax is not None and value_num > rmax:
        return "above_range"
    if rmin is None and rmax is None:
        return None
    return "normal"


def looks_like_unit(token: str) -> bool:
    t = token.lower().strip()
    if t in UNIT_HINTS:
        return True
    if "/" in t or "\u00b5" in t or "\u03bc" in t or "^" in t or "*" in t:
        return True
    if t == "%":
        return True
    return False


def extract_unit_and_range(rest: list[str]) -> tuple[str | None, str]:
    if not rest:
        return None, ""

    if looks_like_unit(rest[0]):
        return rest[0], " ".join(rest[1:])

    return None, " ".join(rest)


HEADER_KEYWORDS = {
    "ESAME",
    "ANALISI",
    "VALORE",
    "UNITA",
    "UNITÀ",
    "RIFERIMENTO",
    "RIF",
    "METODO",
    "DATA",
    "PAZIENTE",
    "CODICE",
}


def parse_lab_lines(text: str) -> list[dict]:
    results: list[dict] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tokens = line.split()
        if len(tokens) < 2:
            continue

        if any(t.upper().strip("():.") in HEADER_KEYWORDS for t in tokens[:3]):
            continue

        idx_val = None
        for i, tok in enumerate(tokens):
            if i == 0:
                continue
            if is_value_token(tok):
                idx_val = i
                break

        if idx_val is None:
            continue

        name = " ".join(tokens[:idx_val]).strip()
        if not name:
            continue

        value_raw = tokens[idx_val]
        rest = tokens[idx_val + 1 :]
        unit, range_str = extract_unit_and_range(rest)

        value_num, value_text = parse_value(value_raw)
        rmin, rmax, rtext = parse_reference(range_str)
        code, display, conf = normalize_exam_name(name)
        flag = compute_flag(value_num, rmin, rmax)

        results.append(
            {
                "test_code": code,
                "test_name_original": name,
                "test_name_normalized": display,
                "value_numeric": value_num,
                "value_text": value_text,
                "unit": unit,
                "reference_min": rmin,
                "reference_max": rmax,
                "reference_text": rtext,
                "flag": flag,
                "method": None,
                "confidence": conf,
            }
        )

    return results


def resolve_document_path(document: Document) -> Path:
    if settings.storage_backend != "local":
        raise NotImplementedError(
            "Estrazione supportata solo con storage locale in questa versione."
        )

    path = LOCAL_STORAGE_ROOT / document.storage_key
    if not path.exists():
        raise FileNotFoundError(f"File documento non trovato: {path}")

    return path


def extract_text_from_pdf(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        chunks = [page.get_text("text") for page in doc]
    finally:
        doc.close()

    return "\n".join(chunks)


def extract_from_document(db: Session, document: Document) -> list[LabTest]:
    """
    Estrae valori da PDF testuali, PDF scansionati o immagini JPEG/PNG.
    Salva i risultati come bozze in lab_tests.
    Idempotente sulle bozze non confermate.
    """
    path = resolve_document_path(document)
    mime = (document.mime_type or "").lower()

    text = ""
    parsed: list[dict] = []
    source = "none"

    if mime == "application/pdf":
        text = extract_text_from_pdf(path)
        parsed = parse_lab_lines(text)

        if parsed:
            source = "pdf-text"
        else:
            logger.info(
                "Nessun valore parseato dal testo PDF del documento %s, provo OCR.",
                document.id,
            )
            ocr_text = extract_text_from_pdf_with_ocr(path)
            if ocr_text and ocr_text.strip():
                text = f"{text}\n{ocr_text}".strip()
                parsed = parse_lab_lines(text)
                source = "pdf-ocr" if parsed else "pdf-none"
            else:
                source = "pdf-none"

    elif is_supported_image_mime(mime):
        text = extract_text_from_image(path)
        parsed = parse_lab_lines(text)
        source = "image-ocr" if parsed else "image-none"

    else:
        raise ValueError(
            "Estrazione supportata solo per PDF e immagini JPEG/PNG in questa versione. "
            "HEIC/TIFF in arrivo."
        )

    db.query(LabTest).filter(
        LabTest.document_id == document.id,
        LabTest.confirmed_by_user.is_(False),
    ).delete(synchronize_session=False)

    created: list[LabTest] = []

    for item in parsed:
        lt = LabTest(
            document_id=document.id,
            patient_id=document.patient_id,
            test_code=item["test_code"],
            test_name_original=item["test_name_original"],
            test_name_normalized=item["test_name_normalized"],
            value_numeric=item["value_numeric"],
            value_text=item["value_text"],
            unit=item["unit"],
            reference_min=item["reference_min"],
            reference_max=item["reference_max"],
            reference_text=item["reference_text"],
            flag=item["flag"],
            method=item["method"],
            confidence=item["confidence"],
            confirmed_by_user=False,
            user_corrected=False,
        )
        db.add(lt)
        created.append(lt)

    document.processing_status = "completed" if created else "pending"
    document.metadata_json = {
        **(document.metadata_json or {}),
        "extraction_source": source,
        "extracted_count": len(created),
        "text_chars": len(text or ""),
        "extracted_at_note": "draft bozze, conferma in Step 2",
    }

    db.commit()

    for lt in created:
        db.refresh(lt)

    logger.info(
        "Estrazione documento %s: source=%s, %d valori bozza",
        document.id,
        source,
        len(created),
    )

    return created