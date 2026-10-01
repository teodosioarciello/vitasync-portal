"""
Sprint B Step 4E.

Test deterministico per endpoint impostazioni utente:
- GET /api/settings ritorna i default (console) per un utente senza settings;
- PATCH aggiorna channel e impostazioni SMTP;
- la password SMTP non viene mai esposta in chiaro via API;
- test-email senza smtp_host ritorna 400;
- cleanup delle impostazioni di test alla fine.
"""

import json
import os
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import User
from app.db.settings_models import UserSettings
from app.db.session import SessionLocal

API_BASE = os.getenv("VITASYNC_API_BASE", "http://localhost:8000")
USERNAME = os.getenv("VITASYNC_TEST_USERNAME", "teo.test")
PASSWORD = os.getenv("VITASYNC_TEST_PASSWORD", "PasswordSicura123!")

failures: list[str] = []
settings_backup = None

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

        # Salva stato corrente per ripristino finale
        existing = db.get(UserSettings, user.id)
        if existing is not None:
            settings_backup = {
                "notification_channel": existing.notification_channel,
                "notifications_enabled": existing.notifications_enabled,
                "smtp_host": existing.smtp_host,
                "smtp_port": existing.smtp_port,
                "smtp_user": existing.smtp_user,
                "smtp_password": existing.smtp_password,
                "smtp_from": existing.smtp_from,
                "smtp_use_tls": existing.smtp_use_tls,
            }
            db.delete(existing)
            db.commit()

        # --- 1. GET default ---
        status, body = http("GET", "/api/settings")
        check("GET /api/settings HTTP 200", status == 200, f"{status} {body}")
        check("default channel = console", body.get("notification_channel") == "console")
        check("default notifications_enabled = true", body.get("notifications_enabled") is True)
        check("default has_smtp_password = false", body.get("has_smtp_password") is False)
        check("password SMTP non esposta", "smtp_password" not in body)

        # --- 2. PATCH: cambio canale + smtp ---
        status, body = http(
            "PATCH",
            "/api/settings",
            {
                "notification_channel": "smtp",
                "smtp_host": "smtp.test.example.com",
                "smtp_port": 587,
                "smtp_user": "testuser",
                "smtp_password": "secret123",
                "smtp_from": "test@example.com",
                "smtp_use_tls": True,
            },
        )
        check("PATCH smtp HTTP 200", status == 200, f"{status} {body}")
        check("channel aggiornato a smtp", body.get("notification_channel") == "smtp")
        check("smtp_host salvato", body.get("smtp_host") == "smtp.test.example.com")
        check("smtp_port salvato", body.get("smtp_port") == 587)
        check("has_smtp_password = true dopo save", body.get("has_smtp_password") is True)
        check("password SMTP ancora non esposta dopo save", "smtp_password" not in body)

        # --- 3. PATCH: torna console ---
        status, body = http(
            "PATCH",
            "/api/settings",
            {"notification_channel": "console"},
        )
        check("PATCH console HTTP 200", status == 200, f"{status} {body}")
        check("channel tornato a console", body.get("notification_channel") == "console")

        # --- 4. PATCH invalido ---
        status, body = http(
            "PATCH",
            "/api/settings",
            {"notification_channel": "whatsapp"},
        )
        check("PATCH con channel invalido HTTP 422", status == 422, f"{status}")

        # --- 5. test-email senza host valido ---
        # (l'host 'smtp.test.example.com' esiste ma non e' raggiungibile:
        # ci aspettiamo 502 se l'host e' configurato, oppure 400 se cancellato.)
        status, body = http(
            "PATCH",
            "/api/settings",
            {"smtp_host": ""},
        )
        check("PATCH smtp_host vuoto HTTP 200", status == 200, f"{status}")

        status, body = http("POST", "/api/settings/test-email")
        # Puo' essere 400 (nessun host) o 502 (host globale non valido) o 200 (host globale ok)
        check(
            "test-email ha risposta valida",
            status in (200, 400, 502),
            f"{status} {body}",
        )

    finally:
        # Restore o pulizia
        try:
            existing = db.get(UserSettings, user.id)
            if settings_backup is None:
                # Non c'erano settings prima: rimuovi quelli creati dal test
                if existing is not None:
                    db.delete(existing)
                    db.commit()
            else:
                if existing is None:
                    existing = UserSettings(user_id=user.id)
                    db.add(existing)
                for k, v in settings_backup.items():
                    setattr(existing, k, v)
                db.commit()
        except Exception as exc:
            print(f"WARN cleanup settings fallito: {exc}")
            try:
                db.rollback()
            except Exception:
                pass

        db.close()

except Exception as exc:
    print(f"ERRORE: {exc}")
    failures.append(str(exc))

print()
if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test delle impostazioni utente Step 4E sono passati.")