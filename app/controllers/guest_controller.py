"""Business logic for guests (Step 4).

All database work lives here — routes only call these functions.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.user import User
from app.schemas.guest_schema import GuestCreate, GuestUpdate
from app.schemas.pagination_schema import PaginationMetadata
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

GUEST_SORT_FIELDS = {
    "created_at": Guest.created_at,
    "phone": Guest.phone,
}


def get_guests(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[Guest], PaginationMetadata]:
    """Search/sort/paginate guest profiles (admin-only route).

    ``search`` matches the related user's name/email plus the profile's
    phone and identification type (case-insensitive, single JOIN query).
    """
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, GUEST_SORT_FIELDS)
    query = db.query(Guest).join(User, Guest.user_id == User.id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            User.name.ilike(pattern)
            | User.email.ilike(pattern)
            | Guest.phone.ilike(pattern)
            | Guest.identification_type.ilike(pattern)
        )
    query = apply_sort(query, column, descending, default=Guest.id.asc())
    return paginate(query, page, page_size)


def get_guest(db: Session, guest_id: int) -> Guest:
    """Return one guest profile or raise 404."""
    guest = db.get(Guest, guest_id)
    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guest {guest_id} not found",
        )
    return guest


def create_guest(db: Session, data: GuestCreate) -> Guest:
    """Create a guest profile for an existing user (one profile per user)."""
    if db.get(User, data.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {data.user_id} not found",
        )
    exists = db.query(Guest).filter(Guest.user_id == data.user_id).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {data.user_id} already has a guest profile",
        )
    guest = Guest(**data.model_dump())
    db.add(guest)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {data.user_id} already has a guest profile",
        )
    db.refresh(guest)
    return guest


def update_guest(db: Session, guest_id: int, data: GuestUpdate) -> Guest:
    """Update only the provided profile fields or raise 404."""
    guest = get_guest(db, guest_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(guest, field, value)
    db.commit()
    db.refresh(guest)
    return guest


def delete_guest(db: Session, guest_id: int) -> Guest:
    """Delete a guest profile or raise 404 (409 while reservations reference it)."""
    guest = get_guest(db, guest_id)
    db.delete(guest)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Guest {guest_id} cannot be deleted while reservations reference it",
        )
    return guest
