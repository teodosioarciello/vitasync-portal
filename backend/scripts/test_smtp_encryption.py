"""
Test deterministico per cifratura SMTP.
Genera una chiave di test al volo e verifica che la password sia cifrata nel DB.
"""
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

# Imposta chiave di test PRIMA di importare user_settings
os.environ["SMTP_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import User
from app.db.settings_models import UserSettings
from app.db.session import SessionLocal
from app.services import user_settings

failures = []
def check(name, ok, details=""):
    print(f"{'OK' if ok else 'FAIL'} {name} | {details}")
    if not ok: failures.append(name)

try:
    db = SessionLocal()
    user = db.query(User).order_by(User.created_at.asc()).first()
    if not user: raise RuntimeError("No user")
    
    # Pulisci
    s = db.get(UserSettings, user.id)
    if s:
        db.delete(s)
        db.commit()
        
    # 1. Update con password
    plain_pwd = "SuperSecret123!"
    user_settings.update_settings(db, user, {"smtp_password": plain_pwd, "smtp_host": "test.com"})
    
    # 2. Leggi dal DB raw
    db.expire_all()
    s_raw = db.get(UserSettings, user.id)
    check("Password nel DB e' cifrata (diversa da plain)", s_raw.smtp_password != plain_pwd, f"raw={s_raw.smtp_password[:20]}...")
    check("Password nel DB sembra Fernet (inizia con gAAAAA)", s_raw.smtp_password.startswith("gAAAAA"), s_raw.smtp_password[:10])
    
    # 3. resolve_effective_smtp
    cfg = user_settings.resolve_effective_smtp(db, user)
    check("resolve_effective_smtp decifra correttamente", cfg["password"] == plain_pwd, cfg["password"])
    
    # 4. settings_to_dict con include_password=True
    d = user_settings.settings_to_dict(s_raw, include_password=True)
    check("settings_to_dict include_password decifra", d["smtp_password"] == plain_pwd)
    
    # 5. settings_to_dict senza include_password
    d2 = user_settings.settings_to_dict(s_raw, include_password=False)
    check("settings_to_dict normale non espone password", "smtp_password" not in d2)
    
    # Cleanup
    db.delete(s_raw)
    db.commit()
    
except Exception as e:
    print(f"ERRORE: {e}")
    failures.append(str(e))
finally:
    db.close()

if failures:
    print("TEST FALLITI")
    sys.exit(1)
print("Tutti i test di cifratura SMTP sono passati.")