"""Pydantic schemas for reservations (Step 5).

The client NEVER sends total_amount, status or created_at —
those are controlled by the backend.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination_schema import PaginationMetadata

# All statuses the system understands. "cancelled" reservations are
# ignored by availability checks; "checked_out" ones cannot be cancelled.
RESERVATION_STATUSES = {"pending", "confirmed", "checked_in", "checked_out", "cancelled"}


class ReservationCreate(BaseModel):
    """Fields the client sends to POST /reservations."""

    guest_id: int
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    guests_count: int = Field(gt=0)


class ReservationUpdate(BaseModel):
    """Safe updatable fields only.

    No id / total_amount / created_at / status here: dates and headcount
    may change, everything else is backend-controlled. Changing dates
    re-checks availability and recalculates the total.
    """

    model_config = ConfigDict(extra="forbid")  # reject protected fields with 422

    check_in: date | None = None
    check_out: date | None = None
    guests_count: int | None = Field(default=None, gt=0)


class ReservationResponse(BaseModel):
    """Reservation data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_id: int
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    guests_count: int
    total_amount: Decimal | None
    status: str
    created_at: datetime
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None


class CheckInResponse(BaseModel):
    """Result of POST /reservations/{id}/check-in (actual DB values)."""

    message: str
    reservation_id: int
    status: str
    checked_in_at: datetime


class CheckOutResponse(BaseModel):
    """Result of POST /reservations/{id}/check-out (actual DB values)."""

    message: str
    reservation_id: int
    status: str
    checked_out_at: datetime


class TodayDashboard(BaseModel):
    """Admin operations snapshot for one business date."""

    date: str
    check_ins: list[ReservationResponse]
    check_outs: list[ReservationResponse]
    currently_checked_in: list[ReservationResponse]


class ReservationListResponse(BaseModel):
    """Paginated reservation results (guests see only their own)."""

    items: list[ReservationResponse]
    pagination: PaginationMetadata
