"""
Migra le password SMTP esistenti in chiaro cifrandole con Fernet.
Richiede SMTP_ENCRYPTION_KEY impostato nell'ambiente.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cryptography.fernet import InvalidToken
from app.db.session import SessionLocal
from app.db.settings_models import UserSettings
from app.services.user_settings import encrypt_smtp_password, _get_fernet

def main():
    f = _get_fernet()
    if not f:
        print("ERRORE: SMTP_ENCRYPTION_KEY non impostata o non valida.")
        print("Genera una chiave con: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        sys.exit(1)

    db = SessionLocal()
    try:
        settings_list = db.query(UserSettings).filter(UserSettings.smtp_password.isnot(None)).all()
        migrated = 0
        for s in settings_list:
            try:
                f.decrypt(s.smtp_password.encode("utf-8"))
                # Gia' cifrato
            except (InvalidToken, Exception):
                # In chiaro
                s.smtp_password = encrypt_smtp_password(s.smtp_password)
                migrated += 1
        db.commit()
        print(f"Migrazione completata: {migrated} password cifrate.")
    finally:
        db.close()

if __name__ == "__main__":
    main()