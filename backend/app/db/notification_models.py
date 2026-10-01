from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    reminder_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reminders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    event: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="reminder_due",
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "channel IN ('console', 'smtp')",
            name="ck_notification_log_channel",
        ),
        CheckConstraint(
            "event IN ('reminder_due')",
            name="ck_notification_log_event",
        ),
        CheckConstraint(
            "status IN ('sent', 'failed', 'skipped')",
            name="ck_notification_log_status",
        ),
    )