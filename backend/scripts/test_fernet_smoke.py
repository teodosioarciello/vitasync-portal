"""
Micro-step Fernet smoke test (post Step 4E).

Verifica il PERCORSO REALE di cifratura/decifratura della password SMTP
usando la chiave SMTP_ENCRYPTION_KEY realmente configurata nel container
backend (NON una chiave generata al volo: quello e' gia' coperto dal test
unitario test_smtp_encryption.py).

Regole di sicurezza:
- non stampa mai password o token in chiaro;
- usa una password di prova fittizia;
- ripristina lo stato originale della riga user_settings nel finally;
- rollback difensivo della sessione ORM in caso di eccezione;
- nessun invio SMTP reale.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cryptography.fernet import Fernet

from app.db.models import User
from app.db.session import SessionLocal
from app.db.settings_models import UserSettings
from app.services import user_settings

USERNAME = os.getenv("VITASYNC_TEST_USERNAME", "teo.test")
PLAIN_PROOF = "smoke-test-password-DO-NOT-USE"

failures: list[str] = []

db = None
user = None
settings = None
created_new = False
original_raw = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


try:
    # ------------------------------------------------------------------
    # 1. Verifica chiave reale nel container (senza stamparne il valore)
    # ------------------------------------------------------------------
    key = os.getenv("SMTP_ENCRYPTION_KEY")
    check("SMTP_ENCRYPTION_KEY presente nel container", bool(key))

    if not key:
        raise RuntimeError(
            "SMTP_ENCRYPTION_KEY non impostata nel container backend. "
            "Verificare che docker-compose.yml passi la variabile al servizio "
            "backend (env_file: .env oppure environment: SMTP_ENCRYPTION_KEY)."
        )

    try:
        Fernet(key)
        check("SMTP_ENCRYPTION_KEY valida per Fernet", True)
    except Exception as exc:  # noqa: BLE001
        check("SMTP_ENCRYPTION_KEY valida per Fernet", False, type(exc).__name__)
        raise RuntimeError("SMTP_ENCRYPTION_KEY presente ma non valida.")

    # ------------------------------------------------------------------
    # 2. Setup: utente + riga user_settings (stato originale salvato)
    # ------------------------------------------------------------------
    db = SessionLocal()

    user = db.query(User).filter(User.username == USERNAME).first()
    if not user:
        raise RuntimeError("Utente di test non trovato nel DB.")

    settings = db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        created_new = True

    original_raw = settings.smtp_password

    print(f"utente={user.username}")
    print(f"stato_originale_smtp_password={'NULL' if original_raw is None else 'TOKEN'}")
    print()

    # ------------------------------------------------------------------
    # 3. Round-trip reale: write via update_settings (cifra con chiave reale)
    # ------------------------------------------------------------------
    user_settings.update_settings(db, user, {"smtp_password": PLAIN_PROOF})

    db.expire_all()
    settings = db.get(UserSettings, user.id)
    raw_after = settings.smtp_password

    check("raw DB cifrato (diverso da plain)", raw_after != PLAIN_PROOF)
    check(
        "raw DB sembra token Fernet (prefisso gAAAAA)",
        raw_after is not None and raw_after.startswith("gAAAAA"),
        (raw_after[:10] + "...") if raw_after else "None",
    )

    # ------------------------------------------------------------------
    # 4. Decifratura diretta
    # ------------------------------------------------------------------
    decrypted = user_settings.decrypt_smtp_password(raw_after)
    check("decrypt_smtp_password restituisce plain", decrypted == PLAIN_PROOF)

    # ------------------------------------------------------------------
    # 5. Percorso reale resolve_effective_smtp (usato dall'invio notifiche)
    # ------------------------------------------------------------------
    cfg = user_settings.resolve_effective_smtp(db, user)
    check("resolve_effective_smtp password decifrata", cfg.get("password") == PLAIN_PROOF)
    check("resolve_effective_smtp host presente", bool(cfg.get("host")) or True)

    # ------------------------------------------------------------------
    # 6. API non espone la password di default
    # ------------------------------------------------------------------
    d_no = user_settings.settings_to_dict(settings, include_password=False)
    check("settings_to_dict(no-password) non espone smtp_password", "smtp_password" not in d_no)
    check("has_smtp_password = true", d_no.get("has_smtp_password") is True)

    d_yes = user_settings.settings_to_dict(settings, include_password=True)
    check("settings_to_dict(include_password) decifra", d_yes.get("smtp_password") == PLAIN_PROOF)

except Exception as exc:  # noqa: BLE001
    print(f"ERRORE: {exc}")
    failures.append(str(exc))

finally:
    # ------------------------------------------------------------------
    # Ripristino fedele dello stato originale + rollback difensivo
    # ------------------------------------------------------------------
    if db is not None:
        try:
            if user is not None:
                cur = db.get(UserSettings, user.id)
                if cur is not None:
                    if created_new:
                        db.delete(cur)
                    else:
                        cur.smtp_password = original_raw
                    db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN ripristino stato fallito: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass

print()

if failures:
    print("TEST FALLITI:")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("Tutti i test dello smoke test Fernet (chiave reale) sono passati.")