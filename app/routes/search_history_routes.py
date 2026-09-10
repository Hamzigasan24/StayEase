"""Search history endpoints (Step 7)."""

from fastapi import APIRouter, Depends, Query, status

from app.controllers import search_history_controller
from app.models.user import User
from app.schemas.search_history_schema import (
    SearchHistoryCreate,
    SearchHistoryResponse,
)
from app.utils.auth import require_guest

router = APIRouter(prefix="/search-history", tags=["Search History"])


@router.post(
    "", response_model=SearchHistoryResponse, status_code=status.HTTP_201_CREATED
)
def create_entry(
    data: SearchHistoryCreate,
    user: User = Depends(require_guest),
):
    """Record one of your searches (owner always comes from the JWT)."""
    return search_history_controller.create_entry(data, user)


@router.get("", response_model=list[SearchHistoryResponse])
def list_entries(
    user_id: int | None = Query(default=None),
    user: User = Depends(require_guest),
):
    """Your searches (admins may pass user_id to inspect someone's)."""
    return search_history_controller.list_entries(user, user_id)


@router.get("/{history_id}", response_model=SearchHistoryResponse)
def read_entry(
    history_id: str,
    user: User = Depends(require_guest),
):
    """One entry (own or admin)."""
    return search_history_controller.get_entry(history_id, user)


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_entry(
    history_id: str,
    user: User = Depends(require_guest),
):
    """Delete an entry (own or admin)."""
    search_history_controller.delete_entry(history_id, user)
    return None
