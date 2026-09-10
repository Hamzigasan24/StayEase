"""Room model (Step 3).

A physical room inside a hotel, of a given room type.
``(hotel_id, room_number)`` is unique: two hotels may both have
a room "101", but one hotel cannot have two rooms "101".
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_number", name="uq_rooms_hotel_room_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id"), nullable=False, index=True
    )
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Many rooms -> one hotel / one room type.
    hotel: Mapped["Hotel"] = relationship(back_populates="rooms")
    room_type: Mapped["RoomType"] = relationship(back_populates="rooms")
    # One room -> many reservations (history is kept: no delete cascade).
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="room")
