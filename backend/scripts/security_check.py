import argparse
import sys
from pathlib import Path


def load_env_file(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def check_security(env):
    errors = []
    warnings = []

    if env.get("ENVIRONMENT") != "production":
        errors.append("ENVIRONMENT deve essere 'production'")

    secret = env.get("SECRET_KEY", "")
    if not secret or "change-me" in secret:
        errors.append("SECRET_KEY non configurata o default")
    elif len(secret) < 32:
        warnings.append("SECRET_KEY corta (%d char, min 32)" % len(secret))

    if env.get("REGISTRATION_MODE") not in ("invite_only", "closed"):
        errors.append("REGISTRATION_MODE deve essere invite_only o closed")
    if env.get("REQUIRE_INVITE_CODE", "").lower() != "true":
        errors.append("REQUIRE_INVITE_CODE deve essere true")

    invite = env.get("INVITE_CODE", "")
    if not invite or "genera-un-codice" in invite:
        errors.append("INVITE_CODE non configurata o default")
    elif len(invite) < 16:
        warnings.append("INVITE_CODE corta (%d char, min 16)" % len(invite))

    if env.get("DEV_AUTO_VERIFY_EMAIL", "").lower() == "true":
        errors.append("DEV_AUTO_VERIFY_EMAIL deve essere false")
    if env.get("DEV_EXPOSE_VERIFICATION_LINK", "").lower() == "true":
        errors.append("DEV_EXPOSE_VERIFICATION_LINK deve essere false")
    if env.get("COOKIE_SECURE", "").lower() != "true":
        errors.append("COOKIE_SECURE deve essere true (richiede HTTPS)")

    cors = env.get("CORS_ORIGINS", "")
    if "localhost" in cors or "127.0.0.1" in cors:
        warnings.append("CORS_ORIGINS contiene localhost: verificare per produzione")

    fernet = env.get("SMTP_ENCRYPTION_KEY", "")
    if not fernet or "chiave-fernet" in fernet:
        errors.append("SMTP_ENCRYPTION_KEY non configurata o default")
    elif len(fernet) < 32:
        warnings.append("SMTP_ENCRYPTION_KEY corta (%d char, min 32)" % len(fernet))

    return errors, warnings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", required=True)
    args = p.parse_args()
    path = Path(args.env_file)
    if not path.exists():
        print("ERRORE: file non trovato:", path)
        return 1
    errors, warnings = check_security(load_env_file(path))
    print("=" * 60)
    print("VITASYNC SECURITY CHECK -", path.name)
    print("=" * 60)
    for e in errors:
        print("  ERRORE:", e)
    for w in warnings:
        print("  WARNING:", w)
    if not errors and not warnings:
        print("  OK: configurazione sicura, deploy remoto consentito.")
        return 0
    if errors:
        print("  ESITO: NON sicuro. Correggi gli errori prima del deploy.")
        return 1
    print("  ESITO: accettabile con warning.")
    return 0


if __name__ == "__main__":
    sys.exit(main())