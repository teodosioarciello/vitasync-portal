"""
Sprint 5.3 - Export Markdown deterministico.
File unico leggibile da umano e da LLM. Nessuna AI: solo dati confermati.
"""
from datetime import date

FLAG_LABEL_IT = {
    "normal": "nella norma",
    "above_range": "sopra range",
    "below_range": "sotto range",
    "critical": "critico",
    "unknown": "n.d.",
}


def _fmt_date(d) -> str:
    if d is None:
        return "-"
    return str(d)


def build_markdown_export(
    *,
    patient: dict,
    confirmed_labs: list,
    therapies: list,
    weights: list,
    bmi_result: dict | None,
    summary: dict,
    anonymize: bool,
    generated_at,
) -> str:
    lines: list = []
    add = lines.append

    name = "Paziente 1" if anonymize else (patient.get("display_name") or "Paziente")

    add("# VitaSync - Export sanitario personale")
    add("")
    add("Generato il: " + generated_at.strftime("%d/%m/%Y %H:%M UTC"))
    add("Versione export: v1")
    add("Ambito: solo valori confermati da documenti attivi")
    add("Profilo: " + name + (" (pseudonimizzato)" if anonymize else ""))
    add("")
    add("## Avviso importante")
    add("")
    add("Questo documento contiene dati sanitari organizzati automaticamente.")
    add("Non costituisce diagnosi, non valuta l'efficacia terapeutica e non")
    add("stabilisce rapporti di causa-effetto tra farmaci e valori.")
    add("Non sostituisce il parere del medico curante.")
    add("")

    add("## Profilo")
    add("")
    add("- Nome: " + name)
    add("- Sesso registrato: " + (patient.get("sex") or "n.d."))
    if anonymize:
        age = patient.get("age_years")
        add("- Eta': " + (str(age) + " anni" if age is not None else "n.d."))
    else:
        add("- Data di nascita: " + _fmt_date(patient.get("birth_date")))
    add("- Minorenne: " + ("si" if patient.get("is_minor") else "no"))
    h = patient.get("height_cm")
    add("- Altezza: " + (str(h) + " cm" if h is not None else "n.d."))
    if weights:
        last_w = weights[0]
        add("- Ultimo peso: " + str(last_w["weight_kg"]) + " kg (" + _fmt_date(last_w["measured_at"]) + ")")
    else:
        add("- Ultimo peso: n.d.")
    if bmi_result and bmi_result.get("has_sufficient_data"):
        add("- BMI: " + str(bmi_result["bmi"]) + " (" + str(bmi_result["category_it"]) + ") - calcolo automatico, non valutazione clinica")
    elif bmi_result and bmi_result.get("is_minor"):
        add("- BMI: non calcolato (paziente minorenne)")
    else:
        add("- BMI: n.d. (dati mancanti)")
    add("")

    add("## Terapie registrate")
    add("")
    active = [t for t in therapies if t.get("status") == "active"]
    if active:
        add("| Medicinale | Principio attivo | Dose | Frequenza | Inizio | Stato |")
        add("|---|---|---|---|---|---|")
        for t in active:
            add("| " + str(t.get("medicine_name") or "-") + " | " + str(t.get("generic_name") or "-") + " | " + str(t.get("dose") or "-") + " | " + str(t.get("frequency") or "-") + " | " + _fmt_date(t.get("start_date")) + " | " + str(t.get("status")) + " |")
    else:
        add("Nessuna terapia attiva registrata.")
    add("")

    add("## Esami confermati (storico)")
    add("")
    by_code: dict = {}
    for lab in confirmed_labs:
        by_code.setdefault(lab["test_code"], []).append(lab)
    if not by_code:
        add("Nessun valore confermato disponibile.")
        add("")
    for code in sorted(by_code):
        pts = sorted(by_code[code], key=lambda p: p.get("document_date") or date.min)
        last = pts[-1]
        head = "### " + str(last.get("test_name_normalized") or code) + " (" + code + ")"
        if last.get("unit"):
            head += " - unita': " + str(last["unit"])
        add(head)
        ref = last.get("reference_text") or ""
        if ref:
            add("Range di riferimento: " + ref)
        add("")
        add("| Data | Valore | Esito | Documento |")
        add("|---|---|---|---|")
        for p in pts:
            if anonymize:
                doc_label = "Referto del " + _fmt_date(p.get("document_date"))
            else:
                doc_label = p.get("document_title") or ("Referto del " + _fmt_date(p.get("document_date")))
            flag_label = FLAG_LABEL_IT.get(p.get("flag"), p.get("flag") or "n.d.")
            add("| " + _fmt_date(p.get("document_date")) + " | " + str(p.get("value_numeric")) + " | " + flag_label + " | " + doc_label + " |")
        add("")

    add("## Segnali deterministici")
    add("")
    alerts = summary.get("alerts", [])
    if alerts:
        for a in alerts:
            add("### " + str(a.get("title_it") or a.get("rule_id")) + " - " + str(a.get("severity")))
            add("")
            add(str(a.get("message_it", "")))
            if a.get("value") is not None:
                add("Valore: " + str(a["value"]) + " " + str(a.get("unit") or "") + " | Riferimento: " + str(a.get("reference") or "-") + " | Data: " + _fmt_date(a.get("document_date")))
            add("")
    else:
        add("Nessun segnale di attenzione rilevato nei dati confermati.")
        add("")

    ctx = summary.get("therapy_context", [])
    if ctx:
        add("## Contesto terapie attive")
        add("")
        for c in ctx:
            add("- " + str(c.get("medicine_name")) + " (" + str(c.get("related_test_name")) + "): " + str(c.get("note_it")))
        add("")

    missing = summary.get("missing_data", [])
    if missing:
        add("## Dati mancanti")
        add("")
        for m in missing:
            add("- " + m)
        add("")

    add("## Limiti di questo export")
    add("")
    add("- Include solo valori confermati dall'utente e documenti attivi.")
    add("- Gli alert sono generati da regole deterministiche, non da AI.")
    add("- Non contiene il testo integrale dei referti.")
    add("- In caso di sintomi acuti o gravi, contattare i servizi di emergenza.")
    add("")

    return "\n".join(lines)