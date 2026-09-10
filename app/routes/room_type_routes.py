"""Room type endpoints (Steps 4 + 11). Thin layer: validation + controller calls."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import room_type_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.room_type_schema import (
    RoomTypeCreate,
    RoomTypeListResponse,
    RoomTypeResponse,
    RoomTypeUpdate,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/room-types", tags=["Room Types"])


@router.post("", response_model=RoomTypeResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(
    data: RoomTypeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new room type (admin-only)."""
    return room_type_controller.create_room_type(db, data)


@router.get("", response_model=RoomTypeListResponse)
def list_room_types(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    search: str | None = Query(default=None),
    min_price: Decimal | None = Query(default=None),
    max_price: Decimal | None = Query(default=None),
    min_capacity: int | None = Query(default=None),
    max_capacity: int | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
):
    """Search room types (name/description, price/capacity ranges) + paging."""
    items, pagination = room_type_controller.get_room_types(
        db, page, page_size, search, min_price, max_price,
        min_capacity, max_capacity, sort_by, sort_order,
    )
    return {"items": items, "pagination": pagination}


@router.get("/{room_type_id}", response_model=RoomTypeResponse)
def read_room_type(room_type_id: int, db: Session = Depends(get_db)):
    """Return one room type (404 when missing)."""
    return room_type_controller.get_room_type(db, room_type_id)


@router.put("/{room_type_id}", response_model=RoomTypeResponse)
def replace_room_type(
    room_type_id: int,
    data: RoomTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update an existing room type (admin-only, 404 when missing)."""
    return room_type_controller.update_room_type(db, room_type_id, data)


@router.delete("/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_room_type(
    room_type_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a room type (admin-only; 404 when missing, 409 while rooms use it)."""
    room_type_controller.delete_room_type(db, room_type_id)
    return None
