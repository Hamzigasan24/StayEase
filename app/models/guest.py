"""Guest model (Step 3).

The guest *profile* of a user: contact details and ID document info.
Exactly one profile per user (``user_id`` is unique).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique FK -> enforces the one-to-one User <-> Guest relationship.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(255))
    identification_type: Mapped[str | None] = mapped_column(String(50))
    identification_number: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # One guest profile -> one user account.
    user: Mapped["User"] = relationship(back_populates="guest")
    # One guest -> many reservations (history is kept: no delete cascade).
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="guest")
