"""
Sprint 5.1c - Calcolo BMI e metriche antropometriche.
Logica pura, nessuna dipendenza da HTTP o DB session.
BMI calcolato SOLO per pazienti adulti con altezza e peso disponibili.
Per i minori: nessun BMI, solo dati grezzi + nota pediatrica.
"""
from datetime import date, timezone


def compute_age_years(birth_date: date | None, reference_date: date | None = None) -> int | None:
    """Calcola eta' in anni completi. Ritorna None se birth_date mancante."""
    if birth_date is None:
        return None
    ref = reference_date or date.today()
    age = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def compute_bmi(weight_kg: float, height_cm: float) -> float:
    """Calcola BMI = peso / (altezza_m ^ 2). Input gia' validati."""
    height_m = height_cm / 100.0
    if height_m <= 0:
        raise ValueError("height_cm deve essere > 0")
    if weight_kg <= 0:
        raise ValueError("weight_kg deve essere > 0")
    return round(weight_kg / (height_m * height_m), 1)


def classify_bmi_adult(bmi: float) -> str:
    """Classificazione BMI adulto (WHO). Non valida per minori."""
    if bmi < 18.5:
        return "underweight"
    if bmi < 25.0:
        return "normal"
    if bmi < 30.0:
        return "overweight"
    return "obese"


def classify_bmi_label_it(bmi: float) -> str:
    """Etichetta BMI in italiano per display."""
    if bmi < 18.5:
        return "sottopeso"
    if bmi < 25.0:
        return "normopeso"
    if bmi < 30.0:
        return "sovrappeso"
    return "obesita'"


def build_bmi_result(
    *,
    weight_kg: float | None,
    height_cm: float | None,
    birth_date: date | None,
    is_minor: bool,
) -> dict:
    """
    Costruisce il risultato BMI completo.
    Ritorna un dict con:
      - bmi: float | None
      - category: str | None (solo adulti)
      - category_it: str | None (solo adulti)
      - is_minor: bool
      - has_sufficient_data: bool
      - note: str | None
    """
    result = {
        "bmi": None,
        "category": None,
        "category_it": None,
        "is_minor": is_minor,
        "has_sufficient_data": False,
        "note": None,
    }

    if weight_kg is None or height_cm is None:
        missing = []
        if weight_kg is None:
            missing.append("peso")
        if height_cm is None:
            missing.append("altezza")
        result["note"] = "Dati mancanti: " + ", ".join(missing) + "."
        return result

    if is_minor:
        result["note"] = (
            "Paziente minorenne: il BMI adulto non viene calcolato. "
            "Per la valutazione della crescita e' necessaria una valutazione pediatrica."
        )
        return result

    try:
        bmi = compute_bmi(weight_kg, height_cm)
    except ValueError as exc:
        result["note"] = f"Dati non validi: {exc}"
        return result

    result["bmi"] = bmi
    result["category"] = classify_bmi_adult(bmi)
    result["category_it"] = classify_bmi_label_it(bmi)
    result["has_sufficient_data"] = True
    return result