"""Hotel endpoints (Steps 4 + 11). Thin layer: validation + controller calls."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import hotel_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.hotel_schema import (
    HotelCreate,
    HotelListResponse,
    HotelResponse,
    HotelUpdate,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/hotels", tags=["Hotels"])


@router.post("", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
def create_hotel(
    data: HotelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new hotel (admin-only)."""
    return hotel_controller.create_hotel(db, data)


@router.get("", response_model=HotelListResponse)
def list_hotels(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    search: str | None = Query(default=None),
    city: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
):
    """Search hotels (name/city/address/description) with paging + sorting."""
    items, pagination = hotel_controller.get_hotels(
        db, page, page_size, search, city, sort_by, sort_order
    )
    return {"items": items, "pagination": pagination}


@router.get("/{hotel_id}", response_model=HotelResponse)
def read_hotel(hotel_id: int, db: Session = Depends(get_db)):
    """Return one hotel (404 when missing)."""
    return hotel_controller.get_hotel(db, hotel_id)


@router.put("/{hotel_id}", response_model=HotelResponse)
def replace_hotel(
    hotel_id: int,
    data: HotelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update an existing hotel (admin-only, 404 when missing)."""
    return hotel_controller.update_hotel(db, hotel_id, data)


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a hotel (admin-only, 404 when missing). Returns no body."""
    hotel_controller.delete_hotel(db, hotel_id)
    return None
