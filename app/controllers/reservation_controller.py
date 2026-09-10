"""Business logic for reservations (Steps 5 + 9).

All database work lives here — routes only call these functions.
Money is always Decimal (never float).

Step 9 lifecycle: pending -> confirmed -> checked_in -> checked_out,
with cancellation allowed only before check-in. Every transition is
enforced here; clients can never set status or timestamps directly.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.activity_log_controller import log_activity
from app.controllers.guest_controller import get_guest
from app.controllers.hotel_controller import get_hotel
from app.controllers.room_controller import get_room
from app.database.mongodb import get_database
from app.models.guest import Guest
from app.models.mongo.notification import build_notification
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.user import User
from app.schemas.pagination_schema import PaginationMetadata
from app.schemas.reservation_schema import ReservationCreate, ReservationUpdate
from app.utils.mongo_helpers import utcnow
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

# Reservations in this state never block a room.
IGNORED_STATUSES = ("cancelled",)

RESERVATION_STATUSES = ("pending", "confirmed", "checked_in", "checked_out", "cancelled")

RESERVATION_SORT_FIELDS = {
    "created_at": Reservation.created_at,
    "check_in": Reservation.check_in,
    "check_out": Reservation.check_out,
    "total_amount": Reservation.total_amount,
    "status": Reservation.status,
}


def get_own_guest(db: Session, user: User) -> Guest:
    """Return the caller's guest profile, creating it on first booking.

    Registration already creates one, so this is only a safety net
    (e.g. for users created before Step 6).
    """
    guest = db.query(Guest).filter(Guest.user_id == user.id).first()
    if guest is None:
        guest = Guest(user_id=user.id)
        db.add(guest)
        db.commit()
        db.refresh(guest)
    return guest


def resolve_booking_guest(db: Session, user: User, guest_id: int) -> Guest:
    """Decide whose guest profile a booking belongs to.

    Admins may book for any existing profile (guest_id is honored).
    Everyone else always books as themselves — a supplied guest_id
    is ignored, never trusted.
    """
    if user.role == "admin":
        return get_guest(db, guest_id)  # 404 for unknown profiles.
    return get_own_guest(db, user)


def resolve_list_scope(
    db: Session, user: User, guest_id: int | None
) -> int | None:
    """Force non-admins to their own profile (403 on another guest's filter).

    Admins keep whatever filter they passed (including none = everything).
    """
    if user.role == "admin":
        return guest_id
    own = get_own_guest(db, user)
    if guest_id is not None and guest_id != own.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view other guests' reservations",
        )
    return own.id


def check_reservation_owner(reservation: Reservation, user: User) -> None:
    """403 unless the caller owns the reservation or is an admin."""
    if user.role != "admin" and reservation.guest.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this reservation",
        )


def _validate_dates(check_in: date, check_out: date) -> None:
    """check_out must be strictly later than check_in (else 400)."""
    if check_out <= check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_out must be later than check_in",
        )


def _check_capacity(room: Room, guests_count: int) -> None:
    """guests_count must fit the room type's capacity (else 400)."""
    capacity = room.room_type.capacity
    if capacity is not None and guests_count > capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room fits at most {capacity} guest(s), got {guests_count}",
        )


def _overlapping_reservation(
    db: Session, room_id: int, check_in: date, check_out: date, exclude_id: int = 0
) -> Reservation | None:
    """Return a conflicting active reservation for the room, if any.

    Two ranges overlap when:
        requested_check_in < existing_check_out
        AND requested_check_out > existing_check_in
    (back-to-back bookings like out=15/in=15 do NOT overlap).
    Cancelled reservations are ignored.
    """
    return (
        db.query(Reservation)
        .filter(
            Reservation.room_id == room_id,
            Reservation.id != exclude_id,
            Reservation.status.notin_(IGNORED_STATUSES),
            Reservation.check_in < check_out,
            Reservation.check_out > check_in,
        )
        .first()
    )


def _ensure_available(
    db: Session, room_id: int, check_in: date, check_out: date, exclude_id: int = 0
) -> None:
    """Raise 409 when the room is already booked for the dates."""
    if _overlapping_reservation(db, room_id, check_in, check_out, exclude_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is not available for the selected dates",
        )


def _calculate_total(room: Room, check_in: date, check_out: date) -> Decimal | None:
    """nights x price_per_night using Decimal only (None price -> None total)."""
    price = room.room_type.price_per_night
    if price is None:
        return None
    nights = (check_out - check_in).days
    return Decimal(price) * nights


def get_reservations(
    db: Session,
    guest_id: int | None = None,
    hotel_id: int | None = None,
    room_id: int | None = None,
    status_filter: str | None = None,
    check_in_from: date | None = None,
    check_in_to: date | None = None,
    check_out_from: date | None = None,
    check_out_to: date | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Reservation], PaginationMetadata]:
    """Filter/sort/paginate reservations (all DB-side).

    Ownership scoping happens in the route via resolve_list_scope;
    unknown status values are rejected with 400 (never a DB error).
    """
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, RESERVATION_SORT_FIELDS)
    if status_filter is not None and status_filter not in RESERVATION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(RESERVATION_STATUSES)}",
        )
    query = db.query(Reservation)
    if guest_id is not None:
        query = query.filter(Reservation.guest_id == guest_id)
    if hotel_id is not None:
        query = query.filter(Reservation.hotel_id == hotel_id)
    if room_id is not None:
        query = query.filter(Reservation.room_id == room_id)
    if status_filter is not None:
        query = query.filter(Reservation.status == status_filter)
    if check_in_from is not None:
        query = query.filter(Reservation.check_in >= check_in_from)
    if check_in_to is not None:
        query = query.filter(Reservation.check_in <= check_in_to)
    if check_out_from is not None:
        query = query.filter(Reservation.check_out >= check_out_from)
    if check_out_to is not None:
        query = query.filter(Reservation.check_out <= check_out_to)
    query = apply_sort(query, column, descending, default=Reservation.id.desc())
    return paginate(query, page, page_size)


def get_reservation(db: Session, reservation_id: int) -> Reservation:
    """Return one reservation or raise 404."""
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reservation {reservation_id} not found",
        )
    return reservation


def create_reservation(db: Session, data: ReservationCreate, user: User) -> Reservation:
    """Validate, price and persist a new reservation (status 'pending').

    The guest profile comes from the authenticated user (admins may
    book for others); a client-supplied guest_id from a non-admin
    is never trusted.
    """
    guest = resolve_booking_guest(db, user, data.guest_id)
    # Steps 1-3: guest, hotel and room must exist (404 otherwise).
    get_hotel(db, data.hotel_id)
    room = get_room(db, data.room_id)
    # Step 4: the room must belong to the given hotel.
    if room.hotel_id != data.hotel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room does not belong to this hotel",
        )
    # Steps 5-7: dates, headcount and capacity.
    _validate_dates(data.check_in, data.check_out)
    _check_capacity(room, data.guests_count)
    # Step 8: no overlapping active reservation (409 on conflict).
    _ensure_available(db, room.id, data.check_in, data.check_out)
    # Steps 9-12: price it, default to 'pending', commit.
    reservation = Reservation(
        guest_id=guest.id,
        hotel_id=data.hotel_id,
        room_id=room.id,
        check_in=data.check_in,
        check_out=data.check_out,
        guests_count=data.guests_count,
        total_amount=_calculate_total(room, data.check_in, data.check_out),
        status="pending",
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create reservation",
        )
    db.refresh(reservation)
    log_activity(
        user.id, "create_reservation", "reservation", reservation.id,
        {"status": reservation.status, "total": str(reservation.total_amount)},
    )
    return reservation


def update_reservation(
    db: Session, reservation_id: int, data: ReservationUpdate
) -> Reservation:
    """Update dates/headcount: re-check availability and recalculate the total."""
    reservation = get_reservation(db, reservation_id)
    changes = data.model_dump(exclude_unset=True)
    new_check_in = changes.get("check_in", reservation.check_in)
    new_check_out = changes.get("check_out", reservation.check_out)
    new_count = changes.get("guests_count", reservation.guests_count)
    _validate_dates(new_check_in, new_check_out)
    _check_capacity(reservation.room, new_count)
    if "check_in" in changes or "check_out" in changes:
        # Exclude this reservation so it never conflicts with itself.
        _ensure_available(
            db, reservation.room_id, new_check_in, new_check_out, exclude_id=reservation.id
        )
        reservation.total_amount = _calculate_total(reservation.room, new_check_in, new_check_out)
    reservation.check_in = new_check_in
    reservation.check_out = new_check_out
    reservation.guests_count = new_count
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update reservation",
        )
    db.refresh(reservation)
    return reservation


def cancel_reservation(db: Session, reservation_id: int) -> Reservation:
    """Mark a reservation 'cancelled' (history is preserved, never deleted).

    Cancellation is only allowed before check-in (pending/confirmed).
    """
    reservation = get_reservation(db, reservation_id)
    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is already cancelled",
        )
    if reservation.status == "checked_out":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checked-out reservation cannot be cancelled",
        )
    if reservation.status == "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checked-in reservation cannot be cancelled",
        )
    reservation.status = "cancelled"
    db.commit()
    db.refresh(reservation)
    log_activity(
        reservation.guest.user_id, "cancel_reservation", "reservation",
        reservation.id, {"status": "cancelled"},
    )
    return reservation


def delete_reservation(db: Session, reservation_id: int) -> Reservation:
    """Hard-delete a reservation (dev/testing only).

    Production systems should prefer cancellation to preserve history.
    """
    reservation = get_reservation(db, reservation_id)
    db.delete(reservation)
    db.commit()
    return reservation


def get_available_rooms_for_dates(
    db: Session,
    hotel_id: int,
    check_in: date,
    check_out: date,
    room_type_id: int | None = None,
) -> list[Room]:
    """Rooms in the hotel free for the whole date range.

    Excludes rooms under 'maintenance' plus rooms with an overlapping
    active reservation. A room with status 'available' can still be
    busy on specific dates — only the overlap check decides that.
    """
    get_hotel(db, hotel_id)  # 404 for unknown hotels.
    _validate_dates(check_in, check_out)
    query = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.status != "maintenance",
    )
    if room_type_id is not None:
        query = query.filter(Room.room_type_id == room_type_id)
    busy_ids = (
        db.query(Reservation.room_id)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.status.notin_(IGNORED_STATUSES),
            Reservation.check_in < check_out,
            Reservation.check_out > check_in,
        )
        .distinct()
    )
    return query.filter(Room.id.notin_(busy_ids)).order_by(Room.id).all()


# ---------------------------------------------------------------------------
# Step 9: check-in / check-out lifecycle.
#
# State machine: pending -> confirmed -> checked_in -> checked_out,
# plus pending/confirmed -> cancelled. Everything else is rejected
# with HTTP 400. Rows are locked (SELECT ... FOR UPDATE) so two
# simultaneous admin requests cannot corrupt reservation/room state.
# ---------------------------------------------------------------------------


def _today() -> date:
    """Business date: server-local calendar day (documented, testable)."""
    return datetime.now().date()


def _paid_total(db: Session, reservation_id: int) -> Decimal:
    """SUM of paid payments for a reservation (0 when none)."""
    value = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.reservation_id == reservation_id, Payment.status == "paid")
        .scalar()
    )
    return Decimal(value)


def _locked_reservation(db: Session, reservation_id: int) -> Reservation:
    """Fetch the reservation with a row lock, or raise 404."""
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .with_for_update()
        .first()
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reservation {reservation_id} not found",
        )
    return reservation


def _notify_stay(owner_id: int, type: str, title: str, message: str) -> None:
    """Best-effort MongoDB notification (never breaks the PG flow)."""
    try:
        get_database().notifications.insert_one(
            build_notification(
                user_id=owner_id, type=type, title=title,
                message=message, created_at=utcnow(),
            )
        )
    except Exception:
        pass


def check_in(db: Session, reservation_id: int) -> Reservation:
    """Admin-only check-in: confirmed + fully paid + due date + free room.

    Atomically sets reservation checked_in (+timestamp) and room occupied.
    Any failure rolls back so reservation and room never disagree.
    """
    reservation = _locked_reservation(db, reservation_id)
    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cancelled reservations cannot be checked in.",
        )
    if reservation.status == "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is already checked in.",
        )
    if reservation.status == "checked_out":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checked-out reservation cannot be checked in.",
        )
    if reservation.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only confirmed reservations can be checked in.",
        )
    # Payment: must be fully covered (a total always exists for priced stays).
    if reservation.total_amount is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation has no total amount; cannot verify payment.",
        )
    balance = Decimal(reservation.total_amount) - _paid_total(db, reservation.id)
    if balance > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reservation has an outstanding balance of {balance}.",
        )
    # Date: on or after the reservation check-in date.
    if _today() < reservation.check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in is only available on or after the reservation check-in date.",
        )
    # Room: must still be free (its id cannot change after booking).
    room = reservation.room
    if room.status != "available":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room is currently '{room.status}' and cannot accept check-in.",
        )
    try:
        reservation.status = "checked_in"
        reservation.checked_in_at = datetime.now(timezone.utc)
        room.status = "occupied"
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not check in.",
        )
    db.refresh(reservation)
    owner_id = reservation.guest.user_id
    _notify_stay(owner_id, "check_in", "Check-in Successful",
                 f"You have successfully checked in for reservation #{reservation.id}.")
    log_activity(owner_id, "check_in", "reservation", reservation.id,
                 {"room_id": room.id, "guest_id": reservation.guest_id})
    return reservation


def check_out(db: Session, reservation_id: int) -> Reservation:
    """Admin-only check-out: checked_in -> checked_out (+timestamp).

    Room occupied -> available; maintenance is preserved. Early checkout
    (before check_out date) is allowed, but never before check_in.
    """
    reservation = _locked_reservation(db, reservation_id)
    if reservation.status == "checked_out":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is already checked out.",
        )
    if reservation.status != "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only checked-in reservations can be checked out.",
        )
    if _today() < reservation.check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-out is not possible before the reservation check-in date.",
        )
    room = reservation.room
    try:
        reservation.status = "checked_out"
        reservation.checked_out_at = datetime.now(timezone.utc)
        if room.status == "occupied":
            room.status = "available"
        # maintenance (or anything else) is deliberately preserved.
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not check out.",
        )
    db.refresh(reservation)
    owner_id = reservation.guest.user_id
    _notify_stay(owner_id, "check_out", "Check-out Successful",
                 f"You have successfully checked out from reservation #{reservation.id}.")
    log_activity(owner_id, "check_out", "reservation", reservation.id,
                 {"room_id": room.id, "guest_id": reservation.guest_id})
    return reservation


def today_dashboard(db: Session) -> dict:
    """Admin snapshot: today's expected check-ins/outs + current guests."""
    today = _today()
    base = db.query(Reservation).order_by(Reservation.id)
    check_ins = base.filter(
        Reservation.check_in == today,
        Reservation.status.in_(("pending", "confirmed")),
    ).all()
    check_outs = base.filter(
        Reservation.check_out == today,
        Reservation.status.in_(("confirmed", "checked_in")),
    ).all()
    current = base.filter(Reservation.status == "checked_in").all()
    return {
        "date": today.isoformat(),
        "check_ins": check_ins,
        "check_outs": check_outs,
        "currently_checked_in": current,
    }
