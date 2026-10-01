"""
Sprint C-media Step 8.

Test deterministico per report retention sicuro.

Crea:
- documento vecchio nel cestino;
- documento recente nel cestino;
- documento attivo.

Esegue report retention con retention 1 giorno solo sui documenti di test.

Verifica:
- il report include solo il documento vecchio;
- nessun documento viene eliminato;
- nessun file viene rimosso;
- nessuna lab-test viene rimossa;
- viene registrato audit document.retention_report.
"""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sqlalchemy import or_

from app.core.config import settings
from app.db.audit_models import AuditLog
from app.db.models import Document, LabTest, User
from app.db.session import SessionLocal
from app.services.document_delete import delete_document_and_file
from app.services.family import ensure_family_and_self_patient
from report_retention_trash import report_retention

LOCAL_STORAGE_ROOT = Path(settings.local_storage_path)

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
RETENTION_DAYS = 1

TITLE_PREFIX = "TEST retention report "
STORAGE_PREFIX = "_fixtures/retention-report-"

failures: list[str] = []

old_id: str | None = None
recent_id: str | None = None
active_id: str | None = None

old_lab_id: str | None = None
recent_lab_id: str | None = None
active_lab_id: str | None = None

old_path: Path | None = None
recent_path: Path | None = None
active_path: Path | None = None


def check(name: str, ok: bool, details: str = "") -> None:
    label = "OK" if ok else "FAIL"
    line = f"{label} {name}"
    if details:
        line += f" | {details}"
    print(line)
    if not ok:
        failures.append(name)


def create_pdf(storage_key: str) -> Path:
    path = LOCAL_STORAGE_ROOT / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% retention report test\n" + b"y" * 80)
    return path


def make_document_with_lab(
    db,
    user: User,
    patient,
    suffix: str,
    deleted_at: datetime | None,
):
    storage_key = f"{STORAGE_PREFIX}{suffix}-{RUN_ID}.pdf"
    path = create_pdf(storage_key)

    document = Document(
        patient_id=patient.id,
        uploaded_by_user_id=user.id,
        title=f"{TITLE_PREFIX}{suffix} {RUN_ID}",
        document_type="lab_report",
        source_filename=path.name,
        storage_key=storage_key,
        mime_type="application/pdf",
        size_bytes=path.stat().st_size,
        sha256="0" * 64,
        processing_status="completed",
        ai_status="disabled",
        metadata_json={"retention_report_test": True, "suffix": suffix},
        deleted_at=deleted_at,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    lab = LabTest(
        document_id=document.id,
        patient_id=patient.id,
        test_code=f"retention_report_{suffix}_{RUN_ID}",
        test_name_original=f"RETENTION REPORT {suffix.upper()}",
        test_name_normalized=f"Retention report {suffix}",
        value_numeric=Decimal("1.0000"),
        unit="u",
        reference_min=Decimal("0.0000"),
        reference_max=Decimal("2.0000"),
        reference_text="0 - 2",
        flag="normal",
        confirmed_by_user=True,
        extracted_at=datetime.now(timezone.utc),
    )

    db.add(lab)
    db.commit()
    db.refresh(lab)

    return document, lab, path


def cleanup_previous(db) -> None:
    previous = (
        db.query(Document)
        .filter(
            or_(
                Document.title.startswith(TITLE_PREFIX),
                Document.storage_key.startswith(STORAGE_PREFIX),
            )
        )
        .all()
    )

    for doc in previous:
        try:
            delete_document_and_file(db, doc)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup precedente fallito per {doc.id}: {exc}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass


try:
    db = SessionLocal()

    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            raise RuntimeError("Nessun utente nel DB. Registra prima un account dal frontend.")

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        cleanup_previous(db)

        now = datetime.now(timezone.utc)

        old_doc, old_lab, old_path = make_document_with_lab(
            db,
            user,
            patient,
            suffix="old",
            deleted_at=now - timedelta(days=RETENTION_DAYS + 1),
        )

        recent_doc, recent_lab, recent_path = make_document_with_lab(
            db,
            user,
            patient,
            suffix="recent",
            deleted_at=now - timedelta(hours=1),
        )

        active_doc, active_lab, active_path = make_document_with_lab(
            db,
            user,
            patient,
            suffix="active",
            deleted_at=None,
        )

        old_id = str(old_doc.id)
        recent_id = str(recent_doc.id)
        active_id = str(active_doc.id)

        old_lab_id = str(old_lab.id)
        recent_lab_id = str(recent_lab.id)
        active_lab_id = str(active_lab.id)

        print("Setup creato:")
        print(f"  old_document_id={old_id}")
        print(f"  recent_document_id={recent_id}")
        print(f"  active_document_id={active_id}")
        print(f"  old_file={old_path}")
        print(f"  recent_file={recent_path}")
        print(f"  active_file={active_path}")
        print()

        candidates = report_retention(
            db,
            days=RETENTION_DAYS,
            only_document_ids=[old_id, recent_id, active_id],
        )

        check(
            "report candidati = 1",
            len(candidates) == 1,
            f"candidates={[c['id'] for c in candidates]}",
        )

        check(
            "report include solo old",
            bool(candidates) and candidates[0]["id"] == old_id,
            f"first_candidate={candidates[0]['id'] if candidates else None}",
        )

        db.expire_all()

        old_after = db.get(Document, UUID(old_id))
        recent_after = db.get(Document, UUID(recent_id))
        active_after = db.get(Document, UUID(active_id))

        old_lab_after = db.get(LabTest, UUID(old_lab_id))
        recent_lab_after = db.get(LabTest, UUID(recent_lab_id))
        active_lab_after = db.get(LabTest, UUID(active_lab_id))

        old_file_after = old_path.exists() if old_path else False
        recent_file_after = recent_path.exists() if recent_path else False
        active_file_after = active_path.exists() if active_path else False

        print()
        print("Verifiche post-report:")
        print(f"  old documento ancora presente: {old_after is not None}")
        print(f"  old ancora nel cestino: {old_after is not None and old_after.deleted_at is not None}")
        print(f"  old lab_test ancora presente: {old_lab_after is not None}")
        print(f"  old file ancora presente: {old_file_after}")
        print(f"  recent documento ancora presente: {recent_after is not None}")
        print(f"  recent ancora nel cestino: {recent_after is not None and recent_after.deleted_at is not None}")
        print(f"  recent lab_test ancora presente: {recent_lab_after is not None}")
        print(f"  recent file ancora presente: {recent_file_after}")
        print(f"  active documento ancora presente: {active_after is not None}")
        print(f"  active non nel cestino: {active_after is not None and active_after.deleted_at is None}")
        print(f"  active lab_test ancora presente: {active_lab_after is not None}")
        print(f"  active file ancora presente: {active_file_after}")
        print()

        check("old documento ancora presente dopo report", old_after is not None)
        check("old ancora nel cestino dopo report", old_after is not None and old_after.deleted_at is not None)
        check("old lab_test ancora presente dopo report", old_lab_after is not None)
        check("old file ancora presente dopo report", old_file_after)

        check("recent documento ancora presente", recent_after is not None)
        check("recent ancora nel cestino", recent_after is not None and recent_after.deleted_at is not None)
        check("recent lab_test ancora presente", recent_lab_after is not None)
        check("recent file ancora presente", recent_file_after)

        check("active documento ancora presente", active_after is not None)
        check("active non nel cestino", active_after is not None and active_after.deleted_at is None)
        check("active lab_test ancora presente", active_lab_after is not None)
        check("active file ancora presente", active_file_after)

        db.expire_all()

        audit_row = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "document.retention_report",
                AuditLog.extra.like(f"%{old_id}%"),
            )
            .order_by(AuditLog.created_at.desc())
            .first()
        )

        check("audit document.retention_report registrato", audit_row is not None)

        if audit_row is not None:
            print()
            print("Audit retention_report trovato:")
            print(f"  action={audit_row.action}")
            print(f"  method={audit_row.method}")
            print(f"  path={audit_row.path}")
            print(f"  user_id={audit_row.user_id}")
            print(f"  extra={audit_row.extra}")
            print()

            check("audit include old id", old_id in (audit_row.extra or ""))
            check("audit non include recent id", recent_id not in (audit_row.extra or ""))
            check("audit non include active id", active_id not in (audit_row.extra or ""))

    finally:
        # Cleanup residui, se ancora presenti.
        try:
            for doc_id in [old_id, recent_id, active_id]:
                if doc_id is None:
                    continue
                document = db.get(Document, UUID(doc_id))
                if document is not None:
                    delete_document_and_file(db, document)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN cleanup finale fallito: {exc}")

        # Cleanup difensivo file residui.
        for path in [old_path, recent_path, active_path]:
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

print("Tutti i test di report retention sicuro sono passati.")