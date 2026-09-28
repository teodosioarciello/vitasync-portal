from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Family, FamilyMember, Patient, PatientAccessGrant, User


def ensure_family_and_self_patient(db: Session, user: User):
    now = datetime.now(timezone.utc)

    owner_member = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.user_id == user.id,
            FamilyMember.role == "owner",
            FamilyMember.status == "active",
        )
        .first()
    )

    if owner_member:
        family = db.get(Family, owner_member.family_id)
    else:
        family = Family(
            name=f"Famiglia {user.full_name or user.username}",
            owner_user_id=user.id,
        )
        db.add(family)
        db.flush()

        db.add(
            FamilyMember(
                family_id=family.id,
                user_id=user.id,
                role="owner",
                status="active",
                joined_at=now,
            )
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.family_id == family.id,
            Patient.relationship_to_owner == "self",
            Patient.legal_representative_user_id == user.id,
        )
        .first()
    )

    if not patient:
        patient = Patient(
            family_id=family.id,
            display_name=user.full_name or user.username,
            birth_date=user.birth_date,
            relationship_to_owner="self",
            is_minor=False,
            legal_representative_user_id=user.id,
            consent_status="self",
        )
        db.add(patient)
        db.flush()

        existing_grant = (
            db.query(PatientAccessGrant)
            .filter(
                PatientAccessGrant.patient_id == patient.id,
                PatientAccessGrant.user_id == user.id,
                PatientAccessGrant.permission == "admin",
            )
            .first()
        )

        if not existing_grant:
            db.add(
                PatientAccessGrant(
                    patient_id=patient.id,
                    user_id=user.id,
                    permission="admin",
                    granted_by_user_id=user.id,
                )
            )

    db.commit()
    db.refresh(family)
    db.refresh(patient)

    return family, patient