"""Reservation endpoints (Steps 5 + 6 auth + 8 payment history).

NOTE: the static ``/available`` route is declared BEFORE
``/{reservation_id}`` so "available" is never mistaken for an id.

Permissions: searching is public; booking/reading/updating/cancelling
needs a signed-in user and is scoped to their own guest profile
(admins bypass ownership); hard delete is admin-only.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import payment_controller, reservation_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.payment_schema import ReservationPaymentHistory
from app.schemas.reservation_schema import (
    CheckInResponse,
    CheckOutResponse,
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationUpdate,
    TodayDashboard,
)
from app.schemas.room_schema import RoomResponse
from app.utils.auth import require_admin, require_guest

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a room",
    description="Validates guest/hotel/room, enforces capacity and date "
    "availability (409 on overlap), and prices the stay server-side. "
    "Requires authentication; books as yourself unless admin.",
    responses={201: {"description": "Reservation created"}, 400: {"description": "Invalid data"}, 404: {"description": "Guest/hotel/room missing"}, 409: {"description": "Room booked for dates"}},
)
def create_reservation(
    data: ReservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Book a room (books as yourself; admins may book for others)."""
    return reservation_controller.create_reservation(db, data, user)


@router.get("", response_model=ReservationListResponse)
def list_reservations(
    guest_id: int | None = Query(default=None),
    hotel_id: int | None = Query(default=None),
    room_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    check_in_from: date | None = Query(default=None),
    check_in_to: date | None = Query(default=None),
    check_out_from: date | None = Query(default=None),
    check_out_to: date | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Search reservations (own scope for guests) with paging + sorting.

    Example: ``/reservations?status=confirmed`` or
    ``/reservations?check_in_from=2026-09-01&check_in_to=2026-09-30``.
    """
    scoped_guest_id = reservation_controller.resolve_list_scope(db, user, guest_id)
    items, pagination = reservation_controller.get_reservations(
        db, scoped_guest_id, hotel_id, room_id, status_filter,
        check_in_from, check_in_to, check_out_from, check_out_to,
        sort_by, sort_order, page, page_size,
    )
    return {"items": items, "pagination": pagination}


@router.get("/available", response_model=list[RoomResponse])
def search_available_rooms(
    hotel_id: int = Query(),
    check_in: date = Query(),
    check_out: date = Query(),
    room_type_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Rooms in a hotel free for the whole date range (public).

    Example: ``/reservations/available?hotel_id=1&check_in=2026-09-15&check_out=2026-09-18``.
    """
    return reservation_controller.get_available_rooms_for_dates(
        db, hotel_id, check_in, check_out, room_type_id
    )


@router.get("/today", response_model=TodayDashboard)
def today_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Admin operations snapshot: today's check-ins/outs + current guests."""
    return reservation_controller.today_dashboard(db)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def read_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Return one reservation (own or admin; 404 when missing)."""
    reservation = reservation_controller.get_reservation(db, reservation_id)
    reservation_controller.check_reservation_owner(reservation, user)
    return reservation


@router.put("/{reservation_id}", response_model=ReservationResponse)
def replace_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Update dates/headcount of your own reservation (re-checks + reprices)."""
    reservation = reservation_controller.get_reservation(db, reservation_id)
    reservation_controller.check_reservation_owner(reservation, user)
    return reservation_controller.update_reservation(db, reservation_id, data)


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Cancel your own reservation (history preserved, never hard-deleted)."""
    reservation = reservation_controller.get_reservation(db, reservation_id)
    reservation_controller.check_reservation_owner(reservation, user)
    return reservation_controller.cancel_reservation(db, reservation_id)


@router.post(
    "/{reservation_id}/check-in",
    response_model=CheckInResponse,
    summary="Admin check-in",
    description="Admin-only. Requires confirmed + fully paid reservation on/after "
    "its check-in date with a free room. Sets room occupied atomically.",
    responses={200: {"description": "Checked in"}, 400: {"description": "Bad state/balance/date"}, 403: {"description": "Admin only"}},
)
def check_in_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Admin check-in: confirmed + fully paid + due date + free room."""
    reservation = reservation_controller.check_in(db, reservation_id)
    return {
        "message": "Guest checked in successfully",
        "reservation_id": reservation.id,
        "status": reservation.status,
        "checked_in_at": reservation.checked_in_at,
    }


@router.post(
    "/{reservation_id}/check-out",
    response_model=CheckOutResponse,
    summary="Admin check-out",
    description="Admin-only. Frees the room (maintenance preserved). Early "
    "checkout allowed, never before the check-in date.",
    responses={200: {"description": "Checked out"}, 400: {"description": "Bad state/date"}, 403: {"description": "Admin only"}},
)
def check_out_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Admin check-out: room occupied -> available (maintenance kept)."""
    reservation = reservation_controller.check_out(db, reservation_id)
    return {
        "message": "Guest checked out successfully",
        "reservation_id": reservation.id,
        "status": reservation.status,
        "checked_out_at": reservation.checked_out_at,
    }


@router.get(
    "/{reservation_id}/payments", response_model=ReservationPaymentHistory
)
def read_reservation_payments(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Balance summary + payment records (own reservation or admin)."""
    return payment_controller.get_reservation_history(db, reservation_id, user)


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a reservation (admin-only, dev/testing; prefer cancellation)."""
    reservation_controller.delete_reservation(db, reservation_id)
    return None
