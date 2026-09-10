"""Room endpoints (Steps 4 + 11). Thin layer: validation + controller calls.

NOTE: the static ``/available`` route is declared BEFORE ``/{room_id}``
so "available" is never mistaken for a room id.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import room_controller, search_history_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.room_schema import (
    AvailableRoomListResponse,
    RoomCreate,
    RoomListResponse,
    RoomResponse,
    RoomUpdate,
)
from app.schemas.search_history_schema import SearchHistoryCreate
from app.utils.auth import get_optional_user, require_admin

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a room (admin-only; hotel and room type must exist)."""
    return room_controller.create_room(db, data)


@router.get("", response_model=RoomListResponse)
def list_rooms(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    hotel_id: int | None = Query(default=None),
    room_type_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    floor: int | None = Query(default=None),
    room_number: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
):
    """Search rooms (hotel/type/status/floor/number) with paging + sorting."""
    items, pagination = room_controller.get_rooms(
        db, page, page_size, hotel_id, room_type_id, status_filter,
        floor, room_number, sort_by, sort_order,
    )
    return {"items": items, "pagination": pagination}


@router.get("/available", response_model=AvailableRoomListResponse)
def list_available_rooms(
    check_in: date | None = Query(default=None),
    check_out: date | None = Query(default=None),
    hotel_id: int | None = Query(default=None),
    room_type_id: int | None = Query(default=None),
    guests_count: int | None = Query(default=None),
    min_price: Decimal | None = Query(default=None),
    max_price: Decimal | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Date-aware availability search (public; enriched hits + paging).

    With dates: excludes maintenance rooms, capacity mismatches and
    overlapping bookings. Without dates: plain status='available' rooms.
    Signed-in searches are recorded to MongoDB search history
    (best-effort; anonymous searches are never stored).
    """
    items, pagination = room_controller.search_available_rooms(
        db, check_in, check_out, hotel_id, room_type_id, guests_count,
        min_price, max_price, page, page_size,
    )
    if user is not None and (check_in is not None or hotel_id is not None
                             or room_type_id is not None or guests_count is not None):
        try:
            search_history_controller.create_entry(
                SearchHistoryCreate(
                    search_query=None, city=None, check_in=check_in,
                    check_out=check_out, guests_count=guests_count,
                ),
                user,
            )
        except Exception:
            pass  # history is secondary; never break the search itself.
    return {"items": items, "pagination": pagination}


@router.get("/{room_id}", response_model=RoomResponse)
def read_room(room_id: int, db: Session = Depends(get_db)):
    """Return one room (404 when missing)."""
    return room_controller.get_room(db, room_id)


@router.put("/{room_id}", response_model=RoomResponse)
def replace_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update an existing room (admin-only, 404 when missing)."""
    return room_controller.update_room(db, room_id, data)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a room (admin-only, 404 when missing). Returns no body."""
    room_controller.delete_room(db, room_id)
    return None
