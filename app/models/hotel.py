"""Hotel model (Step 3).

A hotel owns many rooms and receives many reservations.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # One hotel -> many rooms (rooms are deleted with their hotel).
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="hotel",
        cascade="all, delete-orphan",
    )
    # One hotel -> many reservations (history is kept: no delete cascade).
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="hotel")
