"""
Sprint B Step 4C.

Test deterministico per endpoint GET /api/notifications.

Crea una NotificationLog di test per l'utente corrente,
chiama l'endpoint e verifica che venga restituita.

Non invia email.
Non elimina documenti.
Non tocca retention/purge.
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import User
from app.db.notification_models import NotificationLog
from app.db.session import SessionLocal

# Registra la tabella reminders nel metadata SQLAlchemy per i test standalone
import app.db.therapy_models  # noqa: F401

API_BASE = os.getenv("VITASYNC_API_BASE", "http://localhost:8000")
USERNAME = os.getenv("VITASYNC_TEST_USERNAME", "teo.test")
PASSWORD = os.getenv("VITASYNC_TEST_PASSWORD", "PasswordSicura123!")

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
SUBJECT = f"TEST notification endpoint {RUN_ID}"

cookiejar = CookieJar()
opener = build_opener(HTTPCookieProcessor(cookiejar))

failures: list[str] = []
log_id: UUID | None = None


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

        now = datetime.now(timezone.utc)

        log = NotificationLog(
            reminder_id=None,
            patient_id=None,
            user_id=user.id,
            channel="console",
            event="reminder_due",
            status="sent",
            recipient=user.email or "test@example.com",
            subject=SUBJECT,
            error=None,
            scheduled_for=now,
            sent_at=now,
            metadata_json={"step4c_endpoint_test": True, "run_id": RUN_ID},
        )

        db.add(log)
        db.commit()
        db.refresh(log)

        log_id = log.id

        print(f"notification_log_id={log_id}")
        print(f"user_id={user.id}")
        print()

        status, body = http("GET", "/api/notifications?limit=100")

        check("GET /api/notifications HTTP 200", status == 200, f"{status} {body}")

        if not isinstance(body, list):
            raise RuntimeError(f"Body non lista: {body}")

        found = any(item.get("id") == str(log_id) for item in body)

        check("notifica di test presente nell'elenco", found)

        if found:
            item = next(i for i in body if i.get("id") == str(log_id))
            print()
            print("Notifica trovata:")
            for key in (
                "id",
                "channel",
                "event",
                "status",
                "recipient",
                "subject",
                "sent_at",
                "created_at",
            ):
                print(f"  {key}={item.get(key)}")
            print()

            check("channel console", item.get("channel") == "console")
            check("event reminder_due", item.get("event") == "reminder_due")
            check("status sent", item.get("status") == "sent")
            check("subject atteso", item.get("subject") == SUBJECT)
            check("sent_at popolato", bool(item.get("sent_at")))

        # filtro status
        status, filtered = http("GET", "/api/notifications?limit=100&status=sent")
        check("filtro status=sent HTTP 200", status == 200, f"{status} {filtered}")
        check(
            "filtro status=sent include test",
            isinstance(filtered, list) and any(i.get("id") == str(log_id) for i in filtered),
        )

        status, notFailed = http("GET", "/api/notifications?limit=100&status=failed")
        check("filtro status=failed HTTP 200", status == 200, f"{status} {notFailed}")
        check(
            "filtro status=failed esclude test sent",
            isinstance(notFailed, list) and not any(i.get("id") == str(log_id) for i in notFailed),
        )

    finally:
        if log_id is not None:
            try:
                obj = db.get(NotificationLog, log_id)
                if obj is not None:
                    db.delete(obj)
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                print(f"WARN cleanup notification_log fallito: {exc}")
                try:
                    db.rollback()
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

print("Tutti i test dell'endpoint notifiche Step 4C sono passati.")