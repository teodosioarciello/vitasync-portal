"""
Test deterministico Sprint C-media Step 4.
Verifica il helper audit_identity senza passare dall'HTTP.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_audit_identity.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from types import SimpleNamespace
from uuid import uuid4

from app.services.audit_identity import get_audit_user_id, mark_audit_user


class FakeRequest:
    def __init__(self):
        self.state = SimpleNamespace()


def main() -> int:
    failures: list[str] = []

    uid = uuid4()

    req1 = FakeRequest()
    mark_audit_user(req1, uid)
    got1 = get_audit_user_id(req1)
    if got1 != uid:
        failures.append(f"UUID object: atteso {uid}, ricevuto {got1}")
    else:
        print(f"OK UUID object: {got1}")

    req2 = FakeRequest()
    mark_audit_user(req2, str(uid))
    got2 = get_audit_user_id(req2)
    if got2 != uid:
        failures.append(f"UUID string: atteso {uid}, ricevuto {got2}")
    else:
        print(f"OK UUID string: {got2}")

    req3 = FakeRequest()
    mark_audit_user(req3, "not-a-uuid")
    got3 = get_audit_user_id(req3)
    if got3 is not None:
        failures.append(f"Stringa invalida: atteso None, ricevuto {got3}")
    else:
        print("OK stringa invalida ignorata")

    req4 = FakeRequest()
    mark_audit_user(req4, None)
    got4 = get_audit_user_id(req4)
    if got4 is not None:
        failures.append(f"None: atteso None, ricevuto {got4}")
    else:
        print("OK None ignorato")

    print()
    if failures:
        print("TEST FALLITI:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Tutti i test audit_identity sono passati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())