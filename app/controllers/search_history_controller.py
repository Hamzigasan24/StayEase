"""Business logic for search history (Step 7, MongoDB).

Entries always belong to the JWT identity — clients never send user_id.
Admins may additionally filter by user_id when inspecting.
"""

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.database.mongodb import get_database
from app.models.mongo.search_history import COLLECTION, build_search_history
from app.models.user import User
from app.schemas.search_history_schema import SearchHistoryCreate
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
    """403 unless the caller owns the entry or is an admin."""
    if user.role != "admin" and doc["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this search history",
        )


def create_entry(data: SearchHistoryCreate, user: User) -> dict:
    """Record a search for the authenticated user."""
    doc = build_search_history(
        user_id=user.id,
        search_query=data.search_query,
        city=data.city,
        check_in=data.check_in.isoformat() if data.check_in else None,
        check_out=data.check_out.isoformat() if data.check_out else None,
        guests_count=data.guests_count,
        created_at=utcnow(),
    )
    result = _wrap(lambda: _col().insert_one(doc))
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def list_entries(user: User, user_id: int | None = None) -> list[dict]:
    """Own entries (admins may pass user_id to inspect someone's)."""
    if user.role != "admin":
        if user_id is not None and user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view another user's search history",
            )
        user_id = user.id
    query: dict = {}
    if user_id is not None:
        query["user_id"] = user_id
    docs = _wrap(lambda: list(_col().find(query).sort("created_at", -1)))
    return serialize_many(docs)


def get_entry(history_id: str, user: User) -> dict:
    """One entry (own or admin)."""
    oid = parse_object_id(history_id, "Search history")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search history {history_id} not found",
        )
    _check_owner(doc, user)
    return serialize_doc(doc)


def delete_entry(history_id: str, user: User) -> None:
    """Delete an entry (own or admin)."""
    oid = parse_object_id(history_id, "Search history")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search history {history_id} not found",
        )
    _check_owner(doc, user)
    _wrap(lambda: _col().delete_one({"_id": oid}))
