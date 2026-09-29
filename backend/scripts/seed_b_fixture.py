"""
Fixture di test Sprint B Step 1.
Crea dati SINTETICI per medicinali, terapie e promemoria.
Nessun dato reale.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/seed_b_fixture.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import date, datetime, timedelta, timezone

from app.db.models import User
from app.db.session import SessionLocal
from app.db.therapy_models import Medicine, Reminder, Therapy
from app.services.family import ensure_family_and_self_patient

FIXTURE_MED_NAME = "Paracetamolo 500 mg (fixture)"
FIXTURE_PREFIX = "fixture"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            print("Nessun utente nel DB. Registra prima un account dal frontend.")
            return

        _, patient = ensure_family_and_self_patient(db, user)

        print(f"Utente: {user.username}")
        print(f"Paziente: {patient.display_name} ({patient.id})")
        print()

        # Pulizia fixture precedente, cosi' lo script e' ripetibile.
        old_med = (
            db.query(Medicine)
            .filter(
                Medicine.patient_id == patient.id,
                Medicine.name == FIXTURE_MED_NAME,
            )
            .first()
        )

        if old_med:
            old_therapies = (
                db.query(Therapy)
                .filter(Therapy.medicine_id == old_med.id)
                .all()
            )
            old_therapy_ids = [t.id for t in old_therapies]

            if old_therapy_ids:
                db.query(Reminder).filter(
                    Reminder.therapy_id.in_(old_therapy_ids)
                ).delete(synchronize_session=False)

            for t in old_therapies:
                db.delete(t)

            db.delete(old_med)
            db.commit()
            print("Rimossa precedente fixture terapia.")
            print()

        medicine = Medicine(
            patient_id=patient.id,
            name=FIXTURE_MED_NAME,
            generic_name="Paracetamolo",
            form="compressa",
            strength="500 mg",
            notes="Dato sintetico per test Sprint B.",
            created_by_user_id=user.id,
        )
        db.add(medicine)
        db.commit()
        db.refresh(medicine)

        therapy = Therapy(
            patient_id=patient.id,
            medicine_id=medicine.id,
            status="active",
            start_date=date.today(),
            end_date=None,
            frequency="twice_daily",
            dose="1 compressa",
            route="orale",
            instructions="Assumere dopo i pasti se dolore o febbre.",
            prescribed_by="Medico fixture",
            notes="Terapia sintetica di test.",
            created_by_user_id=user.id,
        )
        db.add(therapy)
        db.commit()
        db.refresh(therapy)

        now = utcnow()

        reminders_data = [
            {
                "title": "Promemoria fixture - dose scaduta",
                "reminder_type": "medication",
                "scheduled_at": now - timedelta(hours=26),
                "therapy_id": therapy.id,
                "notes": "Esempio di promemoria gia' scaduto.",
            },
            {
                "title": "Promemoria fixture - tra 6 ore",
                "reminder_type": "medication",
                "scheduled_at": now + timedelta(hours=6),
                "therapy_id": therapy.id,
                "notes": "Esempio di promemoria futuro vicino.",
            },
            {
                "title": "Promemoria fixture - rinnovo ricetta",
                "reminder_type": "refill",
                "scheduled_at": now + timedelta(days=7),
                "therapy_id": None,
                "notes": "Esempio di promemoria non legato a terapia.",
            },
        ]

        created_reminders = []
        for item in reminders_data:
            reminder = Reminder(
                patient_id=patient.id,
                therapy_id=item["therapy_id"],
                title=item["title"],
                reminder_type=item["reminder_type"],
                scheduled_at=item["scheduled_at"],
                status="pending",
                notes=item["notes"],
                created_by_user_id=user.id,
            )
            db.add(reminder)
            created_reminders.append(reminder)

        db.commit()

        for r in created_reminders:
            db.refresh(r)

        print("Medicinale fixture creato:")
        print(f"  id: {medicine.id}")
        print(f"  nome: {medicine.name}")
        print()

        print("Terapia fixture creata:")
        print(f"  id: {therapy.id}")
        print(f"  stato: {therapy.status}")
        print(f"  frequenza: {therapy.frequency}")
        print(f"  dose: {therapy.dose}")
        print()

        print("Promemoria fixture creati:")
        for r in created_reminders:
            print(f"  - {r.title} ({r.reminder_type}) ore/giorni: {r.scheduled_at.isoformat()}")
        print()

        print("Ora puoi testare le API dopo login.")
        print("Esempio endpoint:")
        print("  GET /api/medicines")
        print("  GET /api/therapies")
        print("  GET /api/reminders")
    finally:
        db.close()


if __name__ == "__main__":
    main()