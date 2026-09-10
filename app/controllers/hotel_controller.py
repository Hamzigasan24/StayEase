"""Business logic for hotels (Step 4).

All database work lives here — routes only call these functions.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.hotel import Hotel
from app.models.room import Room
from app.schemas.hotel_schema import HotelCreate, HotelUpdate
from app.schemas.pagination_schema import PaginationMetadata
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

HOTEL_SORT_FIELDS = {
    "name": Hotel.name,
    "city": Hotel.city,
    "created_at": Hotel.created_at,
}


def get_hotels(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    city: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[dict], PaginationMetadata]:
    """Search/filter/sort/paginate hotels (all DB-side) + room counts.

    ``search`` matches name/city/address/description case-insensitively.
    Returns (item dicts with room counts, pagination metadata).
    """
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, HOTEL_SORT_FIELDS)
    query = db.query(Hotel)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Hotel.name.ilike(pattern)
            | Hotel.city.ilike(pattern)
            | Hotel.address.ilike(pattern)
            | Hotel.description.ilike(pattern)
        )
    if city:
        query = query.filter(Hotel.city.ilike(f"%{city}%"))
    query = apply_sort(query, column, descending, default=Hotel.id.asc())
    hotels, metadata = paginate(query, page, page_size)
    # One GROUP BY for every hotel on the page (no N+1).
    counts: dict[int, dict[str, int]] = {}
    if hotels:
        ids = [h.id for h in hotels]
        for hid, state, num in (
            db.query(Room.hotel_id, Room.status, func.count(Room.id))
            .filter(Room.hotel_id.in_(ids))
            .group_by(Room.hotel_id, Room.status)
            .all()
        ):
            counts.setdefault(hid, {})[state] = num
    items = [
        {
            "id": h.id, "name": h.name, "address": h.address, "city": h.city,
            "description": h.description, "phone": h.phone, "created_at": h.created_at,
            "total_rooms": sum(counts.get(h.id, {}).values()),
            "available_rooms": counts.get(h.id, {}).get("available", 0),
            "occupied_rooms": counts.get(h.id, {}).get("occupied", 0),
            "maintenance_rooms": counts.get(h.id, {}).get("maintenance", 0),
        }
        for h in hotels
    ]
    return items, metadata


def get_hotel(db: Session, hotel_id: int) -> Hotel:
    """Return one hotel or raise 404."""
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel {hotel_id} not found",
        )
    return hotel


def create_hotel(db: Session, data: HotelCreate) -> Hotel:
    """Create and persist a new hotel."""
    hotel = Hotel(**data.model_dump())
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel


def update_hotel(db: Session, hotel_id: int, data: HotelUpdate) -> Hotel:
    """Update only the provided fields or raise 404."""
    hotel = get_hotel(db, hotel_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, value)
    db.commit()
    db.refresh(hotel)
    return hotel


def delete_hotel(db: Session, hotel_id: int) -> Hotel:
    """Delete a hotel (its rooms go with it) or raise 404."""
    hotel = get_hotel(db, hotel_id)
    db.delete(hotel)
    db.commit()
    return hotel
