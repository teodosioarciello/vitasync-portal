"""
Sprint 3 - Test deterministico report PDF.

Verifica:
- collect_report_data include solo valori confermati da documenti attivi;
- esclude valori non confermati;
- esclude valori di documenti nel cestino;
- l'endpoint HTTP risponde 200 con application/pdf e byte %PDF;
- cleanup completo a fine test.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.services.document_delete import delete_document_and_file
from app.services.family import ensure_family_and_self_patient
from app.services.medical_report import collect_report_data

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

API_BASE = os.getenv("VITASYNC_API_BASE", "http://localhost:8000")
USERNAME = os.getenv("VITASYNC_TEST_USERNAME", "teo.test")
PASSWORD = os.getenv("VITASYNC_TEST_PASSWORD", "PasswordSicura123!")

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
CODE_ACTIVE = f"report_pdf_{RUN_ID}"
CODE_TRASH = f"report_pdf_trash_{RUN_ID}"

failures: list[str] = []

doc_active_id = None
doc_trash_id = None
doc_active_path = None
doc_trash_path = None

cookiejar = CookieJar()
opener = build_opener(HTTPCookieProcessor(cookiejar))


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
        with opener.open(req, timeout=60) as resp:
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


def http_bytes(path: str):
    req = Request(API_BASE + path, headers={"Accept": "*/*"}, method="GET")

    try:
        with opener.open(req, timeout=60) as resp:
            return resp.getcode(), resp.headers.get("Content-Type", ""), resp.read()
    except HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", ""), exc.read()


def create_pdf(storage_key: str) -> Path:
    path = LOCAL_STORAGE_ROOT / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% sprint3 report test\n" + b"q" * 80)
    return path


def make_document(db, user, patient, suffix: str):
    storage_key = f"_fixtures/sprint3-report-{suffix}-{RUN_ID}.pdf"
    path = create_pdf(storage_key)

    document = Document(
        patient_id=patient.id,
        uploaded_by_user_id=user.id,
        title=f"TEST sprint3 report {suffix} {RUN_ID}",
        document_type="lab_report",
        source_filename=path.name,
        storage_key=storage_key,
        mime_type="application/pdf",
        size_bytes=path.stat().st_size,
        sha256="0" * 64,
        processing_status="completed",
    )

    db.add(document)
    db.commit()
    db.refresh(document)
    return document, path


def make_lab(db, patient, document, code: str, confirmed: bool, days_ago: int):
    lab = LabTest(
        document_id=document.id,
        patient_id=patient.id,
        test_code=code,
        test_name_original=f"SPRINT3 {code.upper()}",
        test_name_normalized=f"Sprint3 {code}",
        value_numeric=Decimal("1.5000"),
        unit="u",
        reference_min=Decimal("0.0000"),
        reference_max=Decimal("2.0000"),
        reference_text="0 - 2",
        flag="normal",
        confirmed_by_user=confirmed,
        extracted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )

    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


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

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        doc_active, doc_active_path = make_document(db, user, patient, "active")
        doc_trash, doc_trash_path = make_document(db, user, patient, "trash")

        doc_active_id = str(doc_active.id)
        doc_trash_id = str(doc_trash.id)

        make_lab(db, patient, doc_active, CODE_ACTIVE, confirmed=True, days_ago=10)
        make_lab(db, patient, doc_active, CODE_ACTIVE, confirmed=True, days_ago=1)
        make_lab(db, patient, doc_active, CODE_ACTIVE, confirmed=False, days_ago=0)
        make_lab(db, patient, doc_trash, CODE_TRASH, confirmed=True, days_ago=3)

        # soft-delete del secondo documento
        doc_trash.deleted_at = datetime.now(timezone.utc)
        db.commit()

        print("Setup creato:")
        print(f"  doc_active_id={doc_active_id}")
        print(f"  doc_trash_id={doc_trash_id} (nel cestino)")
        print()

        data = collect_report_data(db, patient)

        codes = [g["test_code"] for g in data["groups"]]

        check("codice attivo presente nel report", CODE_ACTIVE in codes)
        check("codice nel cestino assente dal report", CODE_TRASH not in codes)

        group = next((g for g in data["groups"] if g["test_code"] == CODE_ACTIVE), None)

        check("gruppo attivo ha 2 punti (non confermati esclusi)", group is not None and len(group["points"]) == 2, f"points={len(group['points']) if group else None}")

        # ---- HTTP: download PDF ----
        status, ctype, body = http_bytes(
            f"/api/reports/medical-summary.pdf?patient_id={patient.id}"
        )

        check("GET medical-summary.pdf HTTP 200", status == 200, f"{status}")
        check("content-type application/pdf", ctype.startswith("application/pdf"), ctype)
        check("body inizia con %PDF", body[:4] == b"%PDF", str(body[:4]))
        check("body dimensione plausibile", len(body) > 500, f"len={len(body)}")

        status2, ctype2, body2 = http_bytes("/api/reports/medical-summary.pdf")

        check("GET senza patient_id HTTP 200", status2 == 200, f"{status2}")
        check("body2 inizia con %PDF", body2[:4] == b"%PDF", str(body2[:4]))

    finally:
        try:
            for doc_id in [doc_active_id, doc_trash_id]:
                if doc_id is None:
                    continue

                document = db.get(Document, UUID(doc_id))
                if document is not None:
                    delete_document_and_file(db, document)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup finale fallito: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

        for path in [doc_active_path, doc_trash_path]:
            try:
                if path is not None and path.exists():
                    path.unlink()
            except Exception:  # noqa: BLE001
                pass

        db.close()

except Exception as exc:  # noqa: BLE001
    print(f"ERRORE: {exc}")
    failures.append(str(exc))

print()

if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test del report PDF Sprint 3 sono passati.")