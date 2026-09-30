"""
Migrazione Sprint C-media Step 6A.
Aggiunge documents.deleted_at e indice, in modo idempotente.

Da eseguire dentro il container backend:
    docker compose run --rm backend python scripts/migrate_c_media_step6.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text

from app.db.session import engine

STATEMENTS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_documents_deleted_at ON documents (deleted_at)",
]


def main() -> None:
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
            print(f"OK: {stmt}")

    print("Migrazione C-media step 6 completata.")


if __name__ == "__main__":
    main()