"""
Sprint 6.0 - Sintesi narrativa deterministica (zero AI).
Trasforma i dati strutturati (alert 5.2 + profilo + terapie) in prosa prudente
in prima persona, con domande concrete da portare al medico.
Principi: descrive, non interpreta; mai diagnosi; mai causa-effetto;
mai "va tutto bene"; linguaggio condizionale.
"""
from datetime import datetime, timezone


def _join_names(items, key):
    vals = []
    for it in items:
        v = it.get(key)
        if v and v not in vals:
            vals.append(v)
    return ", ".join(vals) if vals else ""


DISCLAIMERS_IT = [
    "Questa sintesi e' generata da regole deterministiche sui tuoi dati confermati. Non e' una diagnosi.",
    "Non valuta l'efficacia delle terapie e non stabilisce rapporti di causa-effetto tra farmaci e valori.",
    "Non sostituisce il parere del medico curante. In caso di sintomi acuti o gravi contatta i servizi di emergenza.",
]

BASE_QUESTIONS_IT = [
    "Quali di questi valori dovrei monitorare nel tempo?",
    "Ci sono esami da ripetere o approfondire?",
    "Le terapie che sto seguendo sono coerenti con questi valori?",
]


def build_health_narrative(
    *,
    patient: dict,
    summary: dict,
    bmi_result: dict | None,
    active_therapies: list,
    weights_count: int,
    confirmed_labs_count: int,
) -> dict:
    alerts = summary.get("alerts", [])
    lab_alerts = [a for a in alerts if a.get("kind") == "lab"]
    trend_alerts = [a for a in alerts if a.get("kind") == "trend"]
    bmi_alerts = [a for a in alerts if a.get("kind") == "measurement"]
    stale_alerts = [a for a in alerts if a.get("kind") == "data"]
    therapy_ctx = summary.get("therapy_context", [])
    status = summary.get("status", "insufficient_data")

    # --- overview ---
    bits = []
    if confirmed_labs_count:
        bits.append(str(confirmed_labs_count) + " valori di laboratorio confermati")
    if weights_count:
        bits.append(str(weights_count) + " misure di peso")
    if active_therapies:
        bits.append(str(len(active_therapies)) + " terapie attive")
    age = patient.get("age_years")
    sex = patient.get("sex") or "non registrato"
    profile = "eta' " + (str(age) + " anni" if age is not None else "n.d.") + ", sesso " + sex
    if bits:
        overview = (
            "Il quadro si basa su " + ", ".join(bits) + ". "
            "Profilo registrato: " + profile + ". "
            "I dati considerati sono solo quelli confermati da te e provenienti da documenti attivi."
        )
    else:
        overview = (
            "Non ci sono ancora dati confermati su cui costruire un quadro. "
            "Profilo registrato: " + profile + "."
        )

    # --- antropometria ---
    if bmi_result and bmi_result.get("is_minor"):
        anthropometry = (
            "Il paziente risulta minorenne: il BMI adulto non viene calcolato. "
            "La valutazione della crescita richiede un pediatra."
        )
    elif bmi_result and bmi_result.get("has_sufficient_data"):
        anthropometry = (
            "BMI calcolato " + str(bmi_result.get("bmi")) + " ("
            + str(bmi_result.get("category_it")) + "). "
            "E' un indicatore di screening basato su altezza e peso registrati, non una valutazione clinica."
        )
    else:
        anthropometry = "Altezza e/o peso non disponibili: il BMI non e' stato calcolato."

    # --- laboratori ---
    if not confirmed_labs_count:
        labs = "Nessun valore di laboratorio confermato disponibile."
    elif lab_alerts:
        names = _join_names(lab_alerts, "test_name")
        labs = (
            "Sono presenti segnali di attenzione su " + str(len(lab_alerts))
            + " esami confermati: " + names + ". "
            "I restanti valori confermati disponibili non risultano fuori range."
        )
    else:
        labs = "I valori di laboratorio confermati disponibili non risultano fuori range."
    if trend_alerts:
        labs += (
            " Su " + str(len(trend_alerts)) + " esami il valore risulta frequentemente "
            "fuori range negli ultimi referti (segnale di trend, non di singola misurazione)."
        )

    # --- terapie ---
    if active_therapies:
        tnames = _join_names(active_therapies, "medicine_name")
        therapies = (
            "Terapie attive registrate: " + tnames + ". "
            "Il sistema non ne valuta efficacia, dosaggi o effetti."
        )
    else:
        therapies = "Nessuna terapia attiva registrata."

    # --- segnali (prosa dagli alert) ---
    signals = [str(a.get("message_it", "")) for a in alerts if a.get("message_it")]

    # --- domande per il medico ---
    questions = []
    if not confirmed_labs_count and not weights_count and not active_therapies:
        questions.append(
            "Non ho ancora dati confermati: quali esami di base dovrei fare per avere un quadro iniziale?"
        )
    else:
        questions.extend(BASE_QUESTIONS_IT)

    seen_codes = set()
    for a in lab_alerts + trend_alerts:
        code = a.get("test_code")
        name = a.get("test_name") or code
        if code in seen_codes:
            continue
        seen_codes.add(code)
        questions.append(
            "Il valore di " + str(name) + " e' risultato fuori range o in trend negativo: "
            "cosa significa nel mio caso e quali passi consigli?"
        )

    if bmi_alerts:
        cat = bmi_alerts[0].get("category_it")
        questions.append(
            "Il mio BMI e' in fascia " + str(cat) + ": e' rilevante nel mio quadro complessivo?"
        )

    if stale_alerts:
        questions.append(
            "E' passato tempo dall'ultimo referto caricato: ha senso programmare un nuovo controllo?"
        )

    if therapy_ctx:
        questions.append(
            "Considerando le mie terapie attive, ci sono esami specifici che dovrei tenere sotto controllo?"
        )

    return {
        "patient_id": str(patient.get("id")),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": overview,
        "anthropometry": anthropometry,
        "labs": labs,
        "therapies": therapies,
        "signals": signals,
        "questions_for_doctor": questions,
        "disclaimers": DISCLAIMERS_IT,
        "missing_data": summary.get("missing_data", []),
    }