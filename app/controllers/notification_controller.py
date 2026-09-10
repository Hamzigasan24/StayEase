"""Business logic for notifications (Step 7, MongoDB).

Every notification has exactly one owner. Non-admins always act on
their own (a supplied user_id is ignored); admins may target any
existing user and list everything.
"""

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError
from sqlalchemy.orm import Session

from app.database.mongodb import get_database
from app.models.mongo.notification import (
    COLLECTION,
    NOTIFICATION_TYPES,
    build_notification,
)
from app.models.user import User
from app.schemas.notification_schema import NotificationCreate
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
    """403 unless the caller owns the notification or is an admin."""
    if user.role != "admin" and doc["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this notification",
        )


def create_notification(db: Session, data: NotificationCreate, user: User) -> dict:
    """Create a notification (owners are self, unless caller is admin)."""
    if data.type not in NOTIFICATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"type must be one of: {', '.join(NOTIFICATION_TYPES)}",
        )
    owner_id = user.id
    if user.role == "admin" and data.user_id is not None:
        if db.get(User, data.user_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {data.user_id} not found",
            )
        owner_id = data.user_id
    doc = build_notification(
        user_id=owner_id,
        type=data.type,
        title=data.title,
        message=data.message,
        created_at=utcnow(),
    )
    result = _wrap(lambda: _col().insert_one(doc))
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def list_notifications(user: User, unread_only: bool = False) -> list[dict]:
    """Own notifications (admins see all), newest first."""
    query: dict = {}
    if user.role != "admin":
        query["user_id"] = user.id
    if unread_only:
        query["is_read"] = False
    docs = _wrap(lambda: list(_col().find(query).sort("created_at", -1)))
    return serialize_many(docs)


def get_notification(notification_id: str, user: User) -> dict:
    """One notification (own or admin)."""
    oid = parse_object_id(notification_id, "Notification")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    _check_owner(doc, user)
    return serialize_doc(doc)


def mark_read(notification_id: str, user: User) -> dict:
    """Mark a notification as read (own or admin)."""
    oid = parse_object_id(notification_id, "Notification")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    _check_owner(doc, user)
    _wrap(lambda: _col().update_one({"_id": oid}, {"$set": {"is_read": True}}))
    return serialize_doc(_wrap(lambda: _col().find_one({"_id": oid})))


def delete_notification(notification_id: str, user: User) -> None:
    """Delete a notification (own or admin)."""
    oid = parse_object_id(notification_id, "Notification")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    _check_owner(doc, user)
    _wrap(lambda: _col().delete_one({"_id": oid}))
