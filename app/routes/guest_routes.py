"""Guest endpoints (Steps 4 + 6 + 11).

Guest profiles are booking data, so every endpoint here is admin-only.
Regular users get their profile auto-created at registration and act
through the reservation endpoints (scoped to themselves).
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import guest_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.guest_schema import GuestCreate, GuestListResponse, GuestResponse, GuestUpdate
from app.utils.auth import require_admin

router = APIRouter(prefix="/guests", tags=["Guests"])


@router.post("", response_model=GuestResponse, status_code=status.HTTP_201_CREATED)
def create_guest(
    data: GuestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a guest profile (admin-only; one profile per user)."""
    return guest_controller.create_guest(db, data)


@router.get("", response_model=GuestListResponse)
def list_guests(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Search guest profiles (user name/email, phone, ID type) + paging."""
    items, pagination = guest_controller.get_guests(
        db, page, page_size, search, sort_by, sort_order
    )
    return {"items": items, "pagination": pagination}


@router.get("/{guest_id}", response_model=GuestResponse)
def read_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Return one guest profile (admin-only, 404 when missing)."""
    return guest_controller.get_guest(db, guest_id)


@router.put("/{guest_id}", response_model=GuestResponse)
def replace_guest(
    guest_id: int,
    data: GuestUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update a guest profile (admin-only, 404 when missing)."""
    return guest_controller.update_guest(db, guest_id, data)


@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a guest profile (admin-only, 404 when missing)."""
    guest_controller.delete_guest(db, guest_id)
    return None
