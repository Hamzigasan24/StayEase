"""Business logic for reviews (Step 7, MongoDB).

Authors always come from the JWT. A review must reference an existing
hotel and one of the author's own reservations (one review per stay).
"""

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError
from sqlalchemy.orm import Session

from app.controllers.hotel_controller import get_hotel
from app.controllers.reservation_controller import get_reservation
from app.database.mongodb import get_database
from app.models.mongo.review import COLLECTION, build_review
from app.models.user import User
from app.schemas.review_schema import ReviewCreate, ReviewUpdate
from app.utils.mongo_helpers import parse_object_id, serialize_doc, serialize_many, utcnow


def _col():
    return get_database()[COLLECTION]


def _wrap(fn, *args, **kwargs):
    """Run a Mongo operation, hiding driver details behind a generic 500."""
    try:
        return fn(*args, **kwargs)
    except PyMongoError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        )


def _check_owner(doc: dict, user: User) -> None:
    """403 unless the caller wrote the review or is an admin."""
    if user.role != "admin" and doc["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this review",
        )


def list_reviews(hotel_id: int | None = None, user_id: int | None = None) -> list[dict]:
    """Return reviews, optionally filtered (public)."""
    query: dict = {}
    if hotel_id is not None:
        query["hotel_id"] = hotel_id
    if user_id is not None:
        query["user_id"] = user_id
    docs = _wrap(lambda: list(_col().find(query).sort("created_at", -1)))
    return serialize_many(docs)


def get_review(review_id: str) -> dict:
    """Return one review or raise 404 (400 on malformed id)."""
    oid = parse_object_id(review_id, "Review")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found",
        )
    return serialize_doc(doc)


def create_review(db: Session, data: ReviewCreate, user: User) -> dict:
    """Create a review as the authenticated user."""
    get_hotel(db, data.hotel_id)  # 404 for unknown hotels.
    reservation = get_reservation(db, data.reservation_id)  # 404 for unknown.
    if reservation.guest.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review your own stays",
        )
    if _wrap(lambda: _col().find_one({"reservation_id": data.reservation_id})) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reservation already has a review",
        )
    doc = build_review(
        user_id=user.id,
        hotel_id=data.hotel_id,
        reservation_id=data.reservation_id,
        rating=data.rating,
        comment=data.comment,
        created_at=utcnow(),
    )
    result = _wrap(lambda: _col().insert_one(doc))
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def update_review(db: Session, review_id: str, data: ReviewUpdate, user: User) -> dict:
    """Update your own review (admins may update any)."""
    oid = parse_object_id(review_id, "Review")
    existing = _wrap(lambda: _col().find_one({"_id": oid}))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found",
        )
    _check_owner(existing, user)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return serialize_doc(existing)
    _wrap(lambda: _col().update_one({"_id": oid}, {"$set": changes}))
    return serialize_doc(_wrap(lambda: _col().find_one({"_id": oid})))


def delete_review(review_id: str, user: User) -> None:
    """Delete your own review (admins may delete any)."""
    oid = parse_object_id(review_id, "Review")
    existing = _wrap(lambda: _col().find_one({"_id": oid}))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found",
        )
    _check_owner(existing, user)
    _wrap(lambda: _col().delete_one({"_id": oid}))
