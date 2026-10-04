import sys
import re
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.health_alerts import build_health_summary
from app.services.health_narrative import build_health_narrative
from app.services.health_metrics import build_bmi_result
from app.services.therapy_test_context import find_therapy_context_for_test

BAD = [r"causato da", r"sospend", r"interromp", r"dosaggio",
       r"va tutto bene", r"sei guarito", r"hai una diagnosi", r"diagnosi di "]

def assert_safe(text_blob, label):
    low = text_blob.lower()
    for pat in BAD:
        assert not re.search(pat, low), f"{label}: pattern vietato: {pat}"

labs = [
    {"test_code": "glucose", "test_name_normalized": "Glucosio", "value_numeric": 180.0,
     "unit": "mg/dL", "reference_min": 70.0, "reference_max": 100.0, "reference_text": "70 - 100",
     "flag": "above_range", "document_date": date(2026, 9, 25)},
    {"test_code": "glucose", "test_name_normalized": "Glucosio", "value_numeric": 112.0,
     "unit": "mg/dL", "reference_min": 70.0, "reference_max": 100.0, "reference_text": "70 - 100",
     "flag": "above_range", "document_date": date(2026, 5, 20)},
    {"test_code": "glucose", "test_name_normalized": "Glucosio", "value_numeric": 95.0,
     "unit": "mg/dL", "reference_min": 70.0, "reference_max": 100.0, "reference_text": "70 - 100",
     "flag": "normal", "document_date": date(2026, 1, 15)},
]
bmi = build_bmi_result(weight_kg=110.0, height_cm=175.0, birth_date=date(1980, 1, 1), is_minor=False)
summary = build_health_summary(
    patient={"id": "p1"}, confirmed_labs=labs, latest_document_date=date(2026, 9, 25),
    bmi_result=bmi, active_medicines=[{"name": "Metformina 500mg", "generic_name": "metformina"}],
    therapy_context_fn=find_therapy_context_for_test,
)
n = build_health_narrative(
    patient={"id": "p1", "sex": "M", "age_years": 46, "is_minor": False},
    summary=summary, bmi_result=bmi,
    active_therapies=[{"medicine_name": "Metformina 500mg", "generic_name": "metformina"}],
    weights_count=3, confirmed_labs_count=len(labs),
)
blob = " ".join([n["overview"], n["anthropometry"], n["labs"], n["therapies"]] + n["signals"] + n["questions_for_doctor"] + n["disclaimers"])
assert_safe(blob, "caso1")
assert "Glucosio" in n["labs"]
assert any("Glucosio" in q for q in n["questions_for_doctor"])
assert all("?" in q for q in n["questions_for_doctor"])
print("Caso 1 OK: lab+trend+BMI+terapia, domande in prima persona, nessun pattern vietato.")

bmi_minor = build_bmi_result(weight_kg=45.0, height_cm=150.0, birth_date=date(2015, 6, 1), is_minor=True)
summary2 = build_health_summary(
    patient={"id": "p2"}, confirmed_labs=labs, latest_document_date=date(2026, 9, 25),
    bmi_result=bmi_minor, active_medicines=[], therapy_context_fn=find_therapy_context_for_test,
)
n2 = build_health_narrative(
    patient={"id": "p2", "sex": "F", "age_years": 11, "is_minor": True},
    summary=summary2, bmi_result=bmi_minor, active_therapies=[],
    weights_count=1, confirmed_labs_count=len(labs),
)
assert "minorenne" in n2["anthropometry"].lower()
assert "pediatra" in n2["anthropometry"].lower()
print("Caso 2 OK: minorenne, BMI non calcolato, nota pediatra.")

summary3 = build_health_summary(
    patient={"id": "p3"}, confirmed_labs=[], latest_document_date=None,
    bmi_result=None, active_medicines=[], therapy_context_fn=find_therapy_context_for_test,
)
n3 = build_health_narrative(
    patient={"id": "p3", "sex": None, "age_years": None, "is_minor": False},
    summary=summary3, bmi_result=None, active_therapies=[],
    weights_count=0, confirmed_labs_count=0,
)
assert n3["status"] == "insufficient_data"
assert any("esami di base" in q for q in n3["questions_for_doctor"])
print("Caso 3 OK: insufficient_data, domanda esami di base.")

print()
print("Tutti i 3 casi narrazione passati.")