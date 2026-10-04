import sys
from pathlib import Path

# Aggiungi la root del backend al sys.path (stesso pattern degli altri script fixture)
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.health_metrics import (
    compute_bmi, classify_bmi_adult, classify_bmi_label_it,
    build_bmi_result, compute_age_years,
)
from datetime import date

# Test 1: BMI normale adulto
bmi = compute_bmi(70.0, 175.0)
cat = classify_bmi_adult(bmi)
lab = classify_bmi_label_it(bmi)
print(f"Test 1 - 70kg/175cm: BMI={bmi}, cat={cat}, label={lab}")
assert 22.0 <= bmi <= 23.0
assert cat == "normal"

# Test 2: BMI sovrappeso
bmi2 = compute_bmi(85.0, 170.0)
cat2 = classify_bmi_adult(bmi2)
print(f"Test 2 - 85kg/170cm: BMI={bmi2}, cat={cat2}")
assert cat2 == "overweight"

# Test 3: Minore -> nessun BMI
r3 = build_bmi_result(weight_kg=45.0, height_cm=150.0, birth_date=date(2015, 6, 1), is_minor=True)
print(f"Test 3 - minore: bmi={r3['bmi']}, note={r3['note'][:60]}")
assert r3["bmi"] is None
assert r3["is_minor"] is True

# Test 4: Dati mancanti
r4 = build_bmi_result(weight_kg=None, height_cm=175.0, birth_date=date(1980, 1, 1), is_minor=False)
print(f"Test 4 - peso mancante: bmi={r4['bmi']}, note={r4['note']}")
assert r4["bmi"] is None
assert "peso" in r4["note"]

# Test 5: compute_age_years
age = compute_age_years(date(1980, 6, 15), date(2026, 10, 4))
print(f"Test 5 - age: {age}")
assert age == 46

# Test 6: BMI obeso
bmi6 = compute_bmi(110.0, 170.0)
cat6 = classify_bmi_adult(bmi6)
print(f"Test 6 - 110kg/170cm: BMI={bmi6}, cat={cat6}")
assert cat6 == "obese"

# Test 7: BMI sottopeso
bmi7 = compute_bmi(45.0, 170.0)
cat7 = classify_bmi_adult(bmi7)
print(f"Test 7 - 45kg/170cm: BMI={bmi7}, cat={cat7}")
assert cat7 == "underweight"

# Test 8: Entrambi mancanti
r8 = build_bmi_result(weight_kg=None, height_cm=None, birth_date=date(1980, 1, 1), is_minor=False)
print(f"Test 8 - entrambi mancanti: bmi={r8['bmi']}, note={r8['note']}")
assert r8["bmi"] is None
assert "peso" in r8["note"] and "altezza" in r8["note"]

print()
print("Tutti gli 8 test BMI passati.")