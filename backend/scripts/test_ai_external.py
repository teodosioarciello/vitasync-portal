import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.ai_external import (
    AI_DISCLAIMER_IT,
    assert_no_identifiers,
    build_ai_user_prompt,
    call_external_ai,
)

print("Test 1: assert_no_identifiers non blocca testo pulito")
clean = "Paziente 1 - Età 46 anni - Glucosio sopra range"
assert_no_identifiers(clean, ["Mario Rossi", "mario.rossi@example.com"], "test1")
print("  OK")

print("Test 2: assert_no_identifiers blocca nome reale")
try:
    assert_no_identifiers("Ciao Mario Rossi, ecco i dati", ["Mario Rossi"], "test2")
    raise AssertionError("Dovrebbe sollevare ValueError")
except ValueError as exc:
    assert "identificatore reale" in str(exc).lower()
    print("  OK: bloccato")

print("Test 3: provider mock ritorna risposta prudente")
res = call_external_ai(
    provider="mock",
    model="mock",
    api_key=None,
    base_url=None,
    system_prompt="system",
    user_prompt="user",
    timeout=5,
    max_prompt_chars=100,
)
assert res["provider"] == "mock"
assert res["stored"] is False
assert res["data_scope"] == "pseudonimizzato"
assert AI_DISCLAIMER_IT in res["disclaimer"]
assert "medico" in res["answer"].lower()
print("  OK: mock response valida")

print("Test 4: provider sconosciuto solleva ValueError")
try:
    call_external_ai(
        provider="badprovider",
        model="x",
        api_key=None,
        base_url=None,
        system_prompt="s",
        user_prompt="u",
    )
    raise AssertionError("Dovrebbe sollevare ValueError")
except ValueError as exc:
    assert "non consentito" in str(exc).lower()
    print("  OK: provider invalido rifiutato")

print("Test 5: prompt utente contiene istruzioni prudenti")
p = build_ai_user_prompt("MARKDOWN")
assert "Non formulare diagnosi" in p
assert "domande" in p.lower()
assert "MARKDOWN" in p
print("  OK")

print("Test 6: ai_assist.py usa solo export pseudonimizzato e guardia privacy")
api_path = BASE_DIR / "app" / "api" / "ai_assist.py"
api_src = api_path.read_text(encoding="utf-8")
assert "anonymize=True" in api_src
assert "assert_no_identifiers" in api_src
assert "settings.ai_external_enabled" in api_src
print("  OK")

print()
print("Tutti i test AI esterna passati.")