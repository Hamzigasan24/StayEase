"""Reservation model (Step 3).

One booking of a room by a guest at a hotel for a date range.
A reservation can have many payments (e.g. deposit + balance).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_id: Mapped[int] = mapped_column(
        ForeignKey("guests.id"), nullable=False, index=True
    )
    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id"), nullable=False, index=True
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"), nullable=False, index=True
    )
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    guests_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Numeric (not float): exact decimal money, e.g. Decimal("259.98").
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    # Step 9: lifecycle timestamps (NULL until the event happens).
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Many reservations -> one guest / one hotel / one room.
    guest: Mapped["Guest"] = relationship(back_populates="reservations")
    hotel: Mapped["Hotel"] = relationship(back_populates="reservations")
    room: Mapped["Room"] = relationship(back_populates="reservations")
    # One reservation -> many payments (deleted with their reservation).
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
    )
