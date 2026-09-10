"""Business logic for room types (Step 4).

All database work lives here — routes only call these functions.
"""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.room_type import RoomType
from app.schemas.pagination_schema import PaginationMetadata
from app.schemas.room_type_schema import RoomTypeCreate, RoomTypeUpdate
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

ROOM_TYPE_SORT_FIELDS = {
    "name": RoomType.name,
    "price_per_night": RoomType.price_per_night,
    "capacity": RoomType.capacity,
    "created_at": RoomType.created_at,
}


def get_room_types(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    min_capacity: int | None = None,
    max_capacity: int | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[RoomType], PaginationMetadata]:
    """Search/filter/sort/paginate room types (all DB-side, Decimal-safe)."""
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, ROOM_TYPE_SORT_FIELDS)
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
    query = db.query(RoomType)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            RoomType.name.ilike(pattern) | RoomType.description.ilike(pattern)
        )
    if min_price is not None:
        query = query.filter(RoomType.price_per_night >= Decimal(min_price))
    if max_price is not None:
        query = query.filter(RoomType.price_per_night <= Decimal(max_price))
    if min_capacity is not None:
        query = query.filter(RoomType.capacity >= min_capacity)
    if max_capacity is not None:
        query = query.filter(RoomType.capacity <= max_capacity)
    query = apply_sort(query, column, descending, default=RoomType.id.asc())
    return paginate(query, page, page_size)


def get_room_type(db: Session, room_type_id: int) -> RoomType:
    """Return one room type or raise 404."""
    room_type = db.get(RoomType, room_type_id)
    if room_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room type {room_type_id} not found",
        )
    return room_type


def create_room_type(db: Session, data: RoomTypeCreate) -> RoomType:
    """Create and persist a new room type."""
    room_type = RoomType(**data.model_dump())
    db.add(room_type)
    db.commit()
    db.refresh(room_type)
    return room_type


def update_room_type(db: Session, room_type_id: int, data: RoomTypeUpdate) -> RoomType:
    """Update only the provided fields or raise 404."""
    room_type = get_room_type(db, room_type_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room_type, field, value)
    db.commit()
    db.refresh(room_type)
    return room_type


def delete_room_type(db: Session, room_type_id: int) -> RoomType:
    """Delete a room type or raise 404.

    The database refuses (FK RESTRICT) while rooms still use the type;
    that surfaces as a 409 conflict instead of a stack trace.
    """
    from sqlalchemy.exc import IntegrityError

    room_type = get_room_type(db, room_type_id)
    db.delete(room_type)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room type {room_type_id} is still used by rooms",
        )
    return room_type
