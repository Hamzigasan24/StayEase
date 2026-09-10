"""Review endpoints (Step 7)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import review_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.review_schema import ReviewCreate, ReviewResponse, ReviewUpdate
from app.utils.auth import require_guest

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    data: ReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Review one of your own stays (hotel + reservation must exist)."""
    return review_controller.create_review(db, data, user)


@router.get("", response_model=list[ReviewResponse])
def list_reviews(
    hotel_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
):
    """Return reviews, optionally filtered by hotel or author (public)."""
    return review_controller.list_reviews(hotel_id, user_id)


@router.get("/{review_id}", response_model=ReviewResponse)
def read_review(review_id: str):
    """Return one review (public; 400 on malformed id, 404 when missing)."""
    return review_controller.get_review(review_id)


@router.put("/{review_id}", response_model=ReviewResponse)
def replace_review(
    review_id: str,
    data: ReviewUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Update your own review (admins may update any)."""
    return review_controller.update_review(db, review_id, data, user)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_review(
    review_id: str,
    user: User = Depends(require_guest),
):
    """Delete your own review (admins may delete any)."""
    review_controller.delete_review(review_id, user)
    return None
