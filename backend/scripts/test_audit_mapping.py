"""
Test deterministico Sprint C-media Step 5/5b/6A.
Verifica che derive_action mappi correttamente le azioni sensibili
di documenti, lab-test, medicinali, terapie, promemoria e auth.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_audit_mapping.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.audit import derive_action

CASES = [
    ("GET", "/api/medicines", None),
    ("POST", "/api/medicines", "medicine.create"),
    ("PATCH", "/api/medicines/123", "medicine.update"),
    ("DELETE", "/api/medicines/123", "medicine.delete"),
    ("GET", "/api/therapies", None),
    ("POST", "/api/therapies", "therapy.create"),
    ("PATCH", "/api/therapies/123", "therapy.update"),
    ("GET", "/api/reminders", None),
    ("POST", "/api/reminders", "reminder.create"),
    ("PATCH", "/api/reminders/123", "reminder.update"),
    ("GET", "/api/documents", None),
    ("GET", "/api/documents/trash", None),
    ("POST", "/api/documents/upload", "document.upload"),
    ("DELETE", "/api/documents/123", "document.soft_delete"),
    ("POST", "/api/documents/123/restore", "document.restore"),
    ("DELETE", "/api/documents/123/permanent", "document.permanent_delete"),
    ("POST", "/api/documents/123/extract", "document.extract"),
    ("POST", "/api/documents/123/lab-tests/confirm-all", "lab_test.confirm_all"),
    ("PATCH", "/api/lab-tests/123", "lab_test.update"),
    ("POST", "/api/auth/login", "auth.login"),
    ("POST", "/api/auth/logout", "auth.logout"),
    ("POST", "/api/auth/register", "auth.register"),
    ("GET", "/api/auth/me", None),
]


def main() -> int:
    failures = []

    for method, path, expected in CASES:
        got = derive_action(method, path)
        if got != expected:
            failures.append(
                f"{method} {path}: atteso {expected!r}, ricevuto {got!r}"
            )
        else:
            print(f"OK {method} {path} -> {got}")

    print()
    if failures:
        print("TEST FALLITI:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Tutti i test di mapping audit sono passati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())