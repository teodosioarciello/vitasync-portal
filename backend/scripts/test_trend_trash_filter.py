"""
Sprint C-media Step 6C.

Prova HTTP deterministica che i documenti nel cestino non alimentano il trend.

Flusso:
1. login API;
2. crea documento + lab-test confermato direttamente in DB;
3. GET /api/lab-tests/trend -> deve contenere 1 punto;
4. DELETE /api/documents/{id} -> soft-delete;
5. GET trend -> deve contenere 0 punti;
6. POST restore -> documento attivo;
7. GET trend -> deve contenere 1 punto;
8. DELETE soft-delete;
9. GET trend -> 0 punti;
10. DELETE permanent;
11. GET trend -> 0 punti;
12. GET documento -> 404.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_trend_trash_filter.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.services.document_delete import delete_document_and_file
from app.services.family import ensure_family_and_self_patient

API_BASE = os.getenv("VITASYNC_API_BASE", "http://localhost:8000")
USERNAME = os.getenv("VITASYNC_TEST_USERNAME", "teo.test")
PASSWORD = os.getenv("VITASYNC_TEST_PASSWORD", "PasswordSicura123!")

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
TEST_CODE = f"trend_trash_{RUN_ID}"
DOC_TITLE = f"TEST trend trash {RUN_ID}"
STORAGE_KEY = f"_fixtures/trend-trash-{RUN_ID}.pdf"

cookiejar = CookieJar()
opener = build_opener(HTTPCookieProcessor(cookiejar))

failures = []
doc_id = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


def http(method: str, path: str, payload=None):
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(API_BASE + path, data=data, headers=headers, method=method)

    try:
        with opener.open(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else None
            return resp.getcode(), body
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return exc.code, body
    except URLError as exc:
        raise RuntimeError(f"API non raggiungibile su {API_BASE}: {exc}") from exc


def trend_count(patient_id: str) -> int:
    status, body = http(
        "GET",
        f"/api/lab-tests/trend?test_code={TEST_CODE}&patient_id={patient_id}",
    )

    if status != 200:
        raise RuntimeError(f"Trend HTTP {status}: {body}")

    if not isinstance(body, dict):
        return 0

    return len(body.get("points", []))


def cleanup() -> None:
    if not doc_id:
        return

    db = SessionLocal()
    try:
        document = db.get(Document, UUID(doc_id))
        if document is not None:
            delete_document_and_file(db, document)
            print("WARN: documento di test ripulito nel finally.")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN cleanup finale fallito: {exc}")
    finally:
        db.close()


try:
    status, login_body = http(
        "POST",
        "/api/auth/login",
        {"identifier": USERNAME, "password": PASSWORD},
    )

    if status != 200:
        raise RuntimeError(f"Login fallito HTTP {status}: {login_body}")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == USERNAME).first()
        if not user:
            raise RuntimeError("Utente di test non trovato nel DB.")

        _, patient = ensure_family_and_self_patient(db, user)
        patient_id = str(patient.id)

        document = Document(
            patient_id=patient.id,
            uploaded_by_user_id=user.id,
            title=DOC_TITLE,
            document_type="lab_report",
            source_filename="trend-trash-proof.pdf",
            storage_key=STORAGE_KEY,
            mime_type="application/pdf",
            size_bytes=1,
            sha256="0" * 64,
            processing_status="completed",
        )

        db.add(document)
        db.commit()
        db.refresh(document)
        doc_id = str(document.id)

        lab = LabTest(
            document_id=document.id,
            patient_id=patient.id,
            test_code=TEST_CODE,
            test_name_original="TREND TRASH PROOF",
            test_name_normalized="Trend trash proof",
            value_numeric=Decimal("1.2300"),
            unit="u",
            reference_min=Decimal("0.0000"),
            reference_max=Decimal("2.0000"),
            reference_text="0 - 2",
            flag="normal",
            confirmed_by_user=True,
        )

        db.add(lab)
        db.commit()
    finally:
        db.close()

    print(f"\ndocument_id={doc_id}")
    print(f"patient_id={patient_id}")
    print(f"test_code={TEST_CODE}\n")

    check("trend conta 1 punto prima del soft-delete", trend_count(patient_id) == 1)

    status, body = http("DELETE", f"/api/documents/{doc_id}")
    check("soft-delete HTTP 200", status == 200, f"{status} {body}")

    check("trend conta 0 punti dopo soft-delete", trend_count(patient_id) == 0)

    status, body = http("POST", f"/api/documents/{doc_id}/restore")
    check("restore HTTP 200", status == 200, f"{status} {body}")

    check("trend conta 1 punto dopo restore", trend_count(patient_id) == 1)

    status, body = http("DELETE", f"/api/documents/{doc_id}")
    check("secondo soft-delete HTTP 200", status == 200, f"{status} {body}")

    check("trend conta 0 punti dopo secondo soft-delete", trend_count(patient_id) == 0)

    status, body = http("DELETE", f"/api/documents/{doc_id}/permanent")
    check("permanent-delete HTTP 200", status == 200, f"{status} {body}")

    check("trend conta 0 punti dopo permanent-delete", trend_count(patient_id) == 0)

    status, body = http("GET", f"/api/documents/{doc_id}")
    check("GET documento dopo permanent HTTP 404", status == 404, f"{status} {body}")

except Exception as exc:  # noqa: BLE001
    print(f"ERRORE: {exc}")
    failures.append(str(exc))
finally:
    cleanup()

print()

if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test di trend/trash filter sono passati.")