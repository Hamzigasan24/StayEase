"""Business logic for activity logs (Step 7, MongoDB).

Append-only: entries are created (by the backend or, manually, by
admins) and read — never updated or deleted. All reads and manual
writes are admin-only so guests cannot forge or snoop on audit data.

``log_activity`` is best-effort: MongoDB trouble must never break the
PostgreSQL flows that call it (login, registration, reservations).
"""

from typing import Any

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.database.mongodb import get_database
from app.models.mongo.activity_log import COLLECTION, build_activity_log
from app.schemas.activity_log_schema import ActivityLogCreate
from app.utils.mongo_helpers import parse_object_id, serialize_doc, serialize_many, utcnow


def _col():
    return get_database()[COLLECTION]


def log_activity(
    user_id: int | None,
    action: str,
    resource: str,
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Backend helper: record an audit entry, swallowing Mongo errors."""
    try:
        _col().insert_one(
            build_activity_log(
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details or {},
                created_at=utcnow(),
            )
        )
    except Exception:
        # Audit logging must never break the request it observes.
        pass


def _wrap(fn, *args, **kwargs):
    """Run a Mongo operation, hiding driver details behind a generic 500."""
    try:
        return fn(*args, **kwargs)
    except PyMongoError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        )


def create_log_entry(data: ActivityLogCreate) -> dict:
    """Manually record an entry (admin-only route)."""
    doc = build_activity_log(
        user_id=data.user_id,
        action=data.action,
        resource=data.resource,
        resource_id=data.resource_id,
        details=data.details,
        created_at=utcnow(),
    )
    result = _wrap(lambda: _col().insert_one(doc))
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def list_logs(
    user_id: int | None = None, action: str | None = None, limit: int = 100
) -> list[dict]:
    """Return log entries, newest first (admin-only route)."""
    query: dict = {}
    if user_id is not None:
        query["user_id"] = user_id
    if action is not None:
        query["action"] = action
    docs = _wrap(lambda: list(_col().find(query).sort("created_at", -1).limit(limit)))
    return serialize_many(docs)


def get_log(log_id: str) -> dict:
    """Return one entry (admin-only route)."""
    oid = parse_object_id(log_id, "Activity log")
    doc = _wrap(lambda: _col().find_one({"_id": oid}))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity log {log_id} not found",
        )
    return serialize_doc(doc)
