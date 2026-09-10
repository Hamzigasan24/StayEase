"""Business logic for rooms (Steps 4 + 11).

All database work lives here — routes only call these functions.
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.hotel_controller import get_hotel
from app.controllers.room_type_controller import get_room_type
from app.models.hotel import Hotel
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.room_type import RoomType
from app.schemas.pagination_schema import PaginationMetadata, build_metadata
from app.schemas.room_schema import ROOM_STATUSES, RoomCreate, RoomUpdate
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

ROOM_SORT_FIELDS = {
    "room_number": Room.room_number,
    "floor": Room.floor,
    "created_at": Room.created_at,
    "status": Room.status,
}


def _duplicate_number(db: Session, hotel_id: int, room_number: str, exclude_id: int = 0) -> bool:
    """True when another room in the same hotel already uses this number."""
    query = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.room_number == room_number,
        Room.id != exclude_id,
    )
    return db.query(query.exists()).scalar()


def get_rooms(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    hotel_id: int | None = None,
    room_type_id: int | None = None,
    status_filter: str | None = None,
    floor: int | None = None,
    room_number: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[Room], PaginationMetadata]:
    """Search/filter/sort/paginate rooms (all DB-side)."""
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, ROOM_SORT_FIELDS)
    if status_filter is not None and status_filter not in ROOM_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(sorted(ROOM_STATUSES))}",
        )
    query = db.query(Room)
    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)
    if room_type_id is not None:
        query = query.filter(Room.room_type_id == room_type_id)
    if status_filter is not None:
        query = query.filter(Room.status == status_filter)
    if floor is not None:
        query = query.filter(Room.floor == floor)
    if room_number:
        query = query.filter(Room.room_number.ilike(f"%{room_number}%"))
    query = apply_sort(query, column, descending, default=Room.id.asc())
    return paginate(query, page, page_size)


def get_available_rooms(
    db: Session,
    hotel_id: int | None = None,
    room_type_id: int | None = None,
) -> list[Room]:
    """Return rooms with status 'available', optionally filtered (legacy helper)."""
    query = db.query(Room).filter(Room.status == "available")
    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)
    if room_type_id is not None:
        query = query.filter(Room.room_type_id == room_type_id)
    return query.order_by(Room.id).all()


def search_available_rooms(
    db: Session,
    check_in: date | None = None,
    check_out: date | None = None,
    hotel_id: int | None = None,
    room_type_id: int | None = None,
    guests_count: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[dict], PaginationMetadata]:
    """Advanced availability search, fully DB-side + paginated enriched hits.

    Rules: dates must form a valid range; guests_count > 0; maintenance
    rooms excluded; capacity must fit; overlapping active reservations
    (cancelled ignored) exclude the room; prices filter on
    room_type.price_per_night (Decimal). Without dates, plain
    status='available' rooms are returned.
    """
    page, page_size = validate_page(page, page_size)
    if (check_in is None) != (check_out is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_in and check_out must be provided together",
        )
    if check_in is not None and check_out <= check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )
    if guests_count is not None and guests_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guests_count must be greater than 0",
        )
    for label, value in (("min_price", min_price), ("max_price", max_price)):
        if value is not None and Decimal(value) < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} must be >= 0",
            )
    if min_price is not None and max_price is not None and Decimal(min_price) > Decimal(max_price):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price must be <= max_price",
        )
    query = (
        db.query(Room, Hotel.name, RoomType.name, RoomType.price_per_night, RoomType.capacity)
        .join(Hotel, Room.hotel_id == Hotel.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .filter(Room.status != "maintenance")
    )
    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)
    if room_type_id is not None:
        query = query.filter(Room.room_type_id == room_type_id)
    if guests_count is not None:
        query = query.filter(RoomType.capacity >= guests_count)
    if min_price is not None:
        query = query.filter(RoomType.price_per_night >= Decimal(min_price))
    if max_price is not None:
        query = query.filter(RoomType.price_per_night <= Decimal(max_price))
    if check_in is not None:
        # Plain 'available' rooms can still be booked for these dates;
        # exclude rooms with an overlapping non-cancelled reservation.
        busy_ids = (
            db.query(Reservation.room_id)
            .filter(
                Reservation.status != "cancelled",
                Reservation.check_in < check_out,
                Reservation.check_out > check_in,
            )
            .distinct()
        )
        query = query.filter(Room.id.notin_(busy_ids))
    else:
        query = query.filter(Room.status == "available")
    query = query.order_by(Room.id.asc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "room_id": room.id,
            "room_number": room.room_number,
            "hotel_id": room.hotel_id,
            "hotel_name": hotel_name,
            "room_type_id": room.room_type_id,
            "room_type_name": type_name,
            "price_per_night": price,
            "capacity": capacity,
            "status": room.status,
        }
        for room, hotel_name, type_name, price, capacity in rows
    ]
    return items, build_metadata(page, page_size, total)


def get_room(db: Session, room_id: int) -> Room:
    """Return one room or raise 404."""
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room {room_id} not found",
        )
    return room


def create_room(db: Session, data: RoomCreate) -> Room:
    """Create a room after verifying hotel, room type and number uniqueness."""
    # 404 when the referenced hotel or room type does not exist.
    get_hotel(db, data.hotel_id)
    get_room_type(db, data.room_type_id)
    if _duplicate_number(db, data.hotel_id, data.room_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room number '{data.room_number}' already exists in hotel {data.hotel_id}",
        )
    room = Room(**data.model_dump())
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room number '{data.room_number}' already exists in hotel {data.hotel_id}",
        )
    db.refresh(room)
    return room


def update_room(db: Session, room_id: int, data: RoomUpdate) -> Room:
    """Update only the provided fields (re-validating FKs/duplicates) or raise 404."""
    room = get_room(db, room_id)
    changes = data.model_dump(exclude_unset=True)
    if "hotel_id" in changes:
        get_hotel(db, changes["hotel_id"])
    if "room_type_id" in changes:
        get_room_type(db, changes["room_type_id"])
    new_hotel = changes.get("hotel_id", room.hotel_id)
    new_number = changes.get("room_number", room.room_number)
    if _duplicate_number(db, new_hotel, new_number, exclude_id=room.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room number '{new_number}' already exists in hotel {new_hotel}",
        )
    for field, value in changes.items():
        setattr(room, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room update conflicts with an existing room",
        )
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: int) -> Room:
    """Delete a room or raise 404 (409 while reservations reference it)."""
    room = get_room(db, room_id)
    db.delete(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room {room_id} cannot be deleted while reservations reference it",
        )
    return room
