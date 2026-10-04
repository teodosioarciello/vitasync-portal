"""
Sprint 5.2 - Motore di alert deterministici.
Regole pure, nessuna dipendenza HTTP.
Output: status + lista alert + note contesto + missing data.
Linguaggio prudente: contesto, mai causa-effetto.
"""
from datetime import date, datetime, timezone
from typing import Any


# Soglie configurabili
STALE_MONTHS = 6
TREND_MIN_POINTS = 3


def _months_between(d1: date, d2: date) -> int:
    return abs((d2.year - d1.year) * 12 + (d2.month - d1.month))


def evaluate_lab_alert(lab: dict) -> dict | None:
    """
    Valuta un singolo lab test. Ritorna un alert dict o None.
    """
    flag = lab.get("flag")
    test_code = lab.get("test_code") or "unknown"
    test_name = lab.get("test_name_normalized") or lab.get("test_name_original") or test_code
    value = lab.get("value_numeric")
    unit = lab.get("unit") or ""
    ref_min = lab.get("reference_min")
    ref_max = lab.get("reference_max")
    ref_text = lab.get("reference_text") or ""
    doc_date = lab.get("document_date")

    if flag == "critical":
        return {
            "rule_id": "lab_critical",
            "severity": "prompt_review",
            "kind": "lab",
            "test_code": test_code,
            "test_name": test_name,
            "value": value,
            "unit": unit,
            "reference": ref_text or _fmt_range(ref_min, ref_max),
            "document_date": str(doc_date) if doc_date else None,
            "message_it": (
                f"Il valore di {test_name} risulta critico nell'ultimo referto confermato. "
                "Consulto medico consigliato in tempi brevi."
            ),
        }

    if flag in ("above_range", "below_range"):
        direction = "sopra" if flag == "above_range" else "sotto"
        return {
            "rule_id": "lab_out_of_range",
            "severity": "attention",
            "kind": "lab",
            "test_code": test_code,
            "test_name": test_name,
            "value": value,
            "unit": unit,
            "reference": ref_text or _fmt_range(ref_min, ref_max),
            "document_date": str(doc_date) if doc_date else None,
            "message_it": (
                f"Il valore di {test_name} risulta {direction} il range di riferimento "
                f"nell'ultimo referto confermato."
            ),
        }

    return None


def _fmt_range(ref_min, ref_max) -> str:
    if ref_min is not None and ref_max is not None:
        return f"{ref_min} - {ref_max}"
    if ref_max is not None:
        return f"< {ref_max}"
    if ref_min is not None:
        return f"> {ref_min}"
    return "-"


def evaluate_trend_alerts(lab_points_by_code: dict[str, list[dict]]) -> list[dict]:
    """
    Valuta trend per ogni test_code. Alert se 3+ punti in peggioramento
    (allontanamento dal range).
    """
    alerts = []
    for code, points in lab_points_by_code.items():
        if len(points) < TREND_MIN_POINTS:
            continue

        # Ordina per data crescente
        sorted_pts = sorted(points, key=lambda p: p.get("document_date") or date.min)
        last_3 = sorted_pts[-TREND_MIN_POINTS:]

        # Conta quanti sono fuori range
        out_count = sum(
            1 for p in last_3
            if p.get("flag") in ("above_range", "below_range", "critical")
        )
        if out_count >= 2:
            test_name = last_3[-1].get("test_name_normalized") or code
            alerts.append({
                "rule_id": "trend_persistent_out_of_range",
                "severity": "attention",
                "kind": "trend",
                "test_code": code,
                "test_name": test_name,
                "points_count": len(sorted_pts),
                "message_it": (
                    f"Negli ultimi {TREND_MIN_POINTS} referti confermati, il valore di "
                    f"{test_name} risulta frequentemente fuori dal range di riferimento. "
                    "Utile discuterne con il medico curante."
                ),
            })

    return alerts


def evaluate_bmi_alert(bmi_result: dict) -> dict | None:
    """
    Valuta BMI (solo adulti). Ritorna alert o None.
    """
    if bmi_result.get("is_minor"):
        return None
    if not bmi_result.get("has_sufficient_data"):
        return None

    category = bmi_result.get("category")
    bmi_val = bmi_result.get("bmi")
    category_it = bmi_result.get("category_it") or category

    if category in ("obese", "underweight"):
        severity = "attention"
        message = (
            f"Il BMI calcolato ({bmi_val}) rientra nella fascia '{category_it}'. "
            "Utile parlarne con il medico curante."
        )
        return {
            "rule_id": f"bmi_{category}",
            "severity": severity,
            "kind": "measurement",
            "bmi": bmi_val,
            "category": category,
            "category_it": category_it,
            "message_it": message,
        }
    if category == "overweight":
        return {
            "rule_id": "bmi_overweight",
            "severity": "watch",
            "kind": "measurement",
            "bmi": bmi_val,
            "category": category,
            "category_it": category_it,
            "message_it": (
                f"Il BMI calcolato ({bmi_val}) rientra nella fascia '{category_it}'. "
                "Da tenere in osservazione."
            ),
        }
    return None


def evaluate_data_staleness(
    latest_document_date: date | None,
    today: date | None = None,
) -> dict | None:
    """
    Alert se ultimo documento è più vecchio di STALE_MONTHS.
    """
    if latest_document_date is None:
        return None
    ref = today or date.today()
    months = _months_between(latest_document_date, ref)
    if months >= STALE_MONTHS:
        return {
            "rule_id": "data_stale",
            "severity": "info",
            "kind": "data",
            "latest_document_date": str(latest_document_date),
            "months_since": months,
            "message_it": (
                f"L'ultimo referto caricato risale a {months} mesi fa "
                f"({latest_document_date}). "
                "Potrebbe essere utile un nuovo controllo."
            ),
        }
    return None


def compute_overall_status(alerts: list[dict]) -> str:
    """
    Calcola lo status complessivo dalla lista di alert.
    """
    if not alerts:
        return "no_attention_signals"

    severities = {a.get("severity") for a in alerts}
    if "prompt_review" in severities:
        return "prompt_review"
    if "attention" in severities:
        return "attention"
    if "watch" in severities:
        return "watch"
    return "no_attention_signals"


def build_health_summary(
    *,
    patient: dict,
    confirmed_labs: list[dict],
    latest_document_date: date | None,
    bmi_result: dict | None,
    active_medicines: list[dict],
    therapy_context_fn,
) -> dict:
    """
    Costruisce il summary completo.
    """
    alerts: list[dict] = []
    missing_data: list[str] = []
    therapy_context: list[dict] = []

    # Labs confermati: serve almeno 1
    if not confirmed_labs:
        return {
            "status": "insufficient_data",
            "alerts": [],
            "therapy_context": [],
            "missing_data": ["Nessun valore di laboratorio confermato disponibile."],
            "patient_id": str(patient.get("id")),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # 1. Alert su ultimo valore per ogni test_code
    latest_by_code: dict[str, dict] = {}
    points_by_code: dict[str, list[dict]] = {}
    for lab in confirmed_labs:
        code = lab.get("test_code") or "unknown"
        points_by_code.setdefault(code, []).append(lab)

    for code, pts in points_by_code.items():
        sorted_pts = sorted(pts, key=lambda p: p.get("document_date") or date.min)
        latest = sorted_pts[-1]
        latest_by_code[code] = latest
        alert = evaluate_lab_alert(latest)
        if alert:
            alerts.append(alert)

    # 2. Trend alerts
    alerts.extend(evaluate_trend_alerts(points_by_code))

    # 3. BMI
    if bmi_result:
        bmi_alert = evaluate_bmi_alert(bmi_result)
        if bmi_alert:
            alerts.append(bmi_alert)
    else:
        missing_data.append("BMI non disponibile (dati peso/altezza mancanti o paziente minorenne).")

    # 4. Data staleness
    stale = evaluate_data_staleness(latest_document_date)
    if stale:
        alerts.append(stale)

    # 5. Contesto terapie: SOLO per test_code che hanno già un alert
    alert_codes = {a.get("test_code") for a in alerts if a.get("kind") == "lab"}
    for code in alert_codes:
        ctx_list = therapy_context_fn(code, active_medicines)
        for ctx in ctx_list:
            ctx["related_test_code"] = code
            ctx["related_test_name"] = latest_by_code.get(code, {}).get(
                "test_name_normalized", code
            )
            therapy_context.append(ctx)

    status = compute_overall_status(alerts)

    return {
        "status": status,
        "alerts": alerts,
        "therapy_context": therapy_context,
        "missing_data": missing_data,
        "patient_id": str(patient.get("id")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }