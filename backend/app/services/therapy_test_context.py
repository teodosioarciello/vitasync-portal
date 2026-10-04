"""
Sprint 5.2 - Mappa di contesto farmaci -> esami comunemente monitorati.
Questa mappa fornisce solo NOTE DI CONTESTO, mai affermazioni di causa-effetto.
"""

# Struttura: keyword (lowercase) su generic_name o name -> lista test_code + nota
THERAPY_TEST_MONITOR_RULES = [
    {
        "id": "statin_liver_muscle",
        "keywords": ["statina", "atorvastatina", "rosuvastatina", "simvastatina", "pravastatina", "atorvastatin", "rosuvastatin", "simvastatin"],
        "test_codes": ["alt", "ast", "ck"],
        "note_it": (
            "Alcuni medicinali di questa classe sono comunemente monitorati "
            "tramite esami epatici (ALT, AST) o muscolari (CK). "
            "Nota di contesto basata sui dati registrati, non diagnosi né rapporto di causa-effetto."
        ),
    },
    {
        "id": "metformin_glucose_b12",
        "keywords": ["metformina", "metformin"],
        "test_codes": ["glucose", "hba1c", "vitamin_b12"],
        "note_it": (
            "Alcuni medicinali di questa classe sono comunemente associati al "
            "monitoraggio di parametri glicemici e vitamina B12. "
            "Nota di contesto, non valutazione terapeutica."
        ),
    },
    {
        "id": "raas_blocker_kidney_potassium",
        "keywords": ["ramipril", "lisinopril", "enalapril", "perindopril", "losartan", "valsartan", "candesartan", "irbesartan", "olmesartan", "telmisartan"],
        "test_codes": ["creatinine", "potassium", "egfr"],
        "note_it": (
            "Alcuni medicinali di questa classe (ACE-inibitori / sartani) sono "
            "comunemente monitorati tramite funzione renale (creatinina, eGFR) "
            "e potassio. Nota di contesto, non diagnosi."
        ),
    },
    {
        "id": "diuretic_electrolyte_kidney",
        "keywords": ["furosemide", "idroclorotiazide", "hydrochlorothiazide", "indapamide", "spironolactone", "espironolattone", "torasemide"],
        "test_codes": ["sodium", "potassium", "creatinine", "uric_acid", "egfr"],
        "note_it": (
            "Alcuni diuretici sono comunemente associati al monitoraggio di "
            "elettroliti (sodio, potassio) e funzione renale. "
            "Nota di contesto, non valutazione clinica."
        ),
    },
    {
        "id": "levothyroxine_thyroid",
        "keywords": ["levotiroxina", "levothyroxine", "euthyrox", "tirosint", "tiroide"],
        "test_codes": ["tsh", "ft4", "ft3"],
        "note_it": (
            "La levotiroxina è comunemente monitorata tramite profilo tiroideo "
            "(TSH, FT4, FT3). Nota di contesto basata sui dati registrati."
        ),
    },
    {
        "id": "corticosteroid_glucose",
        "keywords": ["prednisone", "prednisolone", "cortisone", "desametasone", "metilprednisolone", "betametasone", "dexamethasone"],
        "test_codes": ["glucose", "hba1c"],
        "note_it": (
            "Alcuni corticosteroidi sono comunemente associati al monitoraggio "
            "della glicemia. Nota di contesto, non diagnosi."
        ),
    },
    {
        "id": "nsaid_kidney",
        "keywords": ["ibuprofene", "ibuprofen", "naprossene", "naproxen", "ketoprofene", "ketoprofen", "diclofenac", "indometacina"],
        "test_codes": ["creatinine", "egfr"],
        "note_it": (
            "L'uso prolungato di alcuni FANS può essere associato al monitoraggio "
            "della funzione renale. Nota di contesto, non diagnosi."
        ),
    },
    {
        "id": "anticoagulant_coag",
        "keywords": ["warfarin", "coumadin", "acenocumarolo", "eparina", "enoxaparina"],
        "test_codes": ["inr", "pt"],
        "note_it": (
            "Gli anticoagulanti orali sono comunemente monitorati tramite "
            "esami di coagulazione (INR/PT). Nota di contesto."
        ),
    },
]


def find_therapy_context_for_test(
    test_code: str,
    active_medicines: list[dict],
) -> list[dict]:
    """
    Dato un test_code e una lista di medicinali attivi (dict con name, generic_name),
    ritorna una lista di note di contesto se esiste corrispondenza.
    Ritorna lista vuota se nessuna corrispondenza.
    """
    test_code_lower = (test_code or "").lower().strip()
    if not test_code_lower:
        return []

    results = []
    for med in active_medicines:
        name = (med.get("name") or "").lower().strip()
        generic = (med.get("generic_name") or "").lower().strip()
        searchable = f"{name} {generic}"
        if not searchable.strip():
            continue

        for rule in THERAPY_TEST_MONITOR_RULES:
            if test_code_lower not in rule["test_codes"]:
                continue
            for kw in rule["keywords"]:
                if kw in searchable:
                    results.append({
                        "medicine_name": med.get("name") or generic or "n/d",
                        "generic_name": med.get("generic_name"),
                        "rule_id": rule["id"],
                        "note_it": rule["note_it"],
                        "related_test_codes": rule["test_codes"],
                    })
                    break  # una sola regola per medicina
    return results


def find_all_therapy_context(active_medicines: list[dict]) -> list[dict]:
    """
    Ritorna tutte le note di contesto rilevanti per i medicinali attivi,
    anche senza alert lab. Usato per panoramica generale.
    """
    results = []
    seen_rules = set()
    for med in active_medicines:
        name = (med.get("name") or "").lower().strip()
        generic = (med.get("generic_name") or "").lower().strip()
        searchable = f"{name} {generic}"
        if not searchable.strip():
            continue
        for rule in THERAPY_TEST_MONITOR_RULES:
            if rule["id"] in seen_rules:
                continue
            for kw in rule["keywords"]:
                if kw in searchable:
                    results.append({
                        "medicine_name": med.get("name") or generic or "n/d",
                        "generic_name": med.get("generic_name"),
                        "rule_id": rule["id"],
                        "note_it": rule["note_it"],
                        "related_test_codes": rule["test_codes"],
                    })
                    seen_rules.add(rule["id"])
                    break
    return results