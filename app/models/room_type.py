"""Room type model (Step 3).

A room type (e.g. "Deluxe Double") describes a category of rooms:
its price per night and how many people it fits. Many physical
rooms can share one room type.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Numeric (not float): exact decimal money, e.g. Decimal("129.99").
    price_per_night: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    capacity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # One room type -> many rooms.
    # No delete cascade: a type in use by rooms cannot be deleted
    # while rooms still reference it (foreign key RESTRICT).
    rooms: Mapped[list["Room"]] = relationship(back_populates="room_type")
