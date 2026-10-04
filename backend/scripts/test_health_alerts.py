"""
Test unitari per health_alerts.py
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import date, datetime, timezone
from app.services.health_alerts import (
    evaluate_lab_alert,
    evaluate_trend_alerts,
    evaluate_bmi_alert,
    evaluate_data_staleness,
    build_health_summary,
    compute_overall_status,
)
from app.services.therapy_test_context import find_therapy_context_for_test

print("Test 1: Lab critico -> prompt_review")
lab_critical = {
    "test_code": "glucose",
    "test_name_normalized": "Glucosio",
    "value_numeric": 500.0,
    "unit": "mg/dL",
    "reference_min": 70.0,
    "reference_max": 100.0,
    "reference_text": "70 - 100",
    "flag": "critical",
    "document_date": date(2026, 9, 25),
}
alert1 = evaluate_lab_alert(lab_critical)
assert alert1 is not None
assert alert1["severity"] == "prompt_review"
assert alert1["rule_id"] == "lab_critical"
print(f"  OK: {alert1['message_it'][:60]}...")

print("\nTest 2: Lab fuori range -> attention")
lab_above = {
    "test_code": "glucose",
    "test_name_normalized": "Glucosio",
    "value_numeric": 120.0,
    "unit": "mg/dL",
    "reference_min": 70.0,
    "reference_max": 100.0,
    "reference_text": "70 - 100",
    "flag": "above_range",
    "document_date": date(2026, 9, 25),
}
alert2 = evaluate_lab_alert(lab_above)
assert alert2 is not None
assert alert2["severity"] == "attention"
assert alert2["rule_id"] == "lab_out_of_range"
assert "sopra" in alert2["message_it"]
print(f"  OK: {alert2['message_it'][:60]}...")

print("\nTest 3: Trend peggioramento (3 punti fuori range) -> attention")
points = {
    "glucose": [
        {"test_code": "glucose", "test_name_normalized": "Glucosio", "flag": "above_range", "document_date": date(2026, 1, 15)},
        {"test_code": "glucose", "test_name_normalized": "Glucosio", "flag": "above_range", "document_date": date(2026, 5, 20)},
        {"test_code": "glucose", "test_name_normalized": "Glucosio", "flag": "above_range", "document_date": date(2026, 9, 25)},
    ]
}
alerts3 = evaluate_trend_alerts(points)
assert len(alerts3) == 1
assert alerts3[0]["rule_id"] == "trend_persistent_out_of_range"
assert alerts3[0]["severity"] == "attention"
print(f"  OK: {alerts3[0]['message_it'][:60]}...")

print("\nTest 4: BMI adulto obeso -> attention")
bmi_obese = {
    "bmi": 35.2,
    "category": "obese",
    "category_it": "obesità",
    "is_minor": False,
    "has_sufficient_data": True,
}
alert4 = evaluate_bmi_alert(bmi_obese)
assert alert4 is not None
assert alert4["rule_id"] == "bmi_obese"
assert alert4["severity"] == "attention"
print(f"  OK: {alert4['message_it'][:60]}...")

print("\nTest 5: BMI adulto sovrappeso -> watch")
bmi_over = {
    "bmi": 27.5,
    "category": "overweight",
    "category_it": "sovrappeso",
    "is_minor": False,
    "has_sufficient_data": True,
}
alert5 = evaluate_bmi_alert(bmi_over)
assert alert5 is not None
assert alert5["rule_id"] == "bmi_overweight"
assert alert5["severity"] == "watch"
print(f"  OK: {alert5['message_it'][:60]}...")

print("\nTest 6: Dati insufficienti -> insufficient_data")
summary6 = build_health_summary(
    patient={"id": "test-patient"},
    confirmed_labs=[],
    latest_document_date=None,
    bmi_result=None,
    active_medicines=[],
    therapy_context_fn=find_therapy_context_for_test,
)
assert summary6["status"] == "insufficient_data"
assert len(summary6["missing_data"]) > 0
print(f"  OK: status={summary6['status']}")

print("\nTest 7: Contesto terapia (lab alert + metformina) -> nota contesto")
labs_with_glucose = [
    {
        "test_code": "glucose",
        "test_name_normalized": "Glucosio",
        "value_numeric": 130.0,
        "unit": "mg/dL",
        "reference_min": 70.0,
        "reference_max": 100.0,
        "reference_text": "70 - 100",
        "flag": "above_range",
        "document_date": date(2026, 9, 25),
    }
]
medicines = [
    {"name": "Metformina 500mg", "generic_name": "metformina"},
]
summary7 = build_health_summary(
    patient={"id": "test-patient"},
    confirmed_labs=labs_with_glucose,
    latest_document_date=date(2026, 9, 25),
    bmi_result=None,
    active_medicines=medicines,
    therapy_context_fn=find_therapy_context_for_test,
)
assert summary7["status"] == "attention"
assert len(summary7["alerts"]) > 0
assert len(summary7["therapy_context"]) > 0
ctx = summary7["therapy_context"][0]
assert ctx["rule_id"] == "metformin_glucose_b12"
assert "monitoraggio" in ctx["note_it"].lower()
print(f"  OK: terapia={ctx['medicine_name']}, nota={ctx['note_it'][:50]}...")

print("\nTest 8: Status complessivo con prompt_review")
alerts_mixed = [
    {"severity": "attention", "rule_id": "test1"},
    {"severity": "prompt_review", "rule_id": "test2"},
    {"severity": "watch", "rule_id": "test3"},
]
status8 = compute_overall_status(alerts_mixed)
assert status8 == "prompt_review"
print(f"  OK: status={status8}")

print("\nTest 9: Data staleness (>6 mesi) -> info")
stale_date = date(2026, 1, 1)
today = date(2026, 10, 4)
alert9 = evaluate_data_staleness(stale_date, today)
assert alert9 is not None
assert alert9["rule_id"] == "data_stale"
assert alert9["severity"] == "info"
assert alert9["months_since"] >= 6
print(f"  OK: {alert9['message_it'][:60]}...")

print("\n" + "="*60)
print("Tutti i 9 test superati!")
print("="*60)