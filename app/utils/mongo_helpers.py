"""Reusable MongoDB helpers (Step 7).

ObjectId and datetime objects are not JSON-serializable, so every
controller converts documents with ``serialize_doc`` before returning
them: ``_id`` becomes the string field ``id``, datetimes become
ISO-8601 strings. ``parse_object_id`` turns path params into ObjectIds
and raises a clean 400 for garbage input.
"""

from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status


def parse_object_id(value: str, resource: str = "Document") -> ObjectId:
    """Convert a path parameter to ObjectId or raise 400."""
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {resource.lower()} id: {value!r}",
        )


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for new documents."""
    from datetime import timezone

    return datetime.now(timezone.utc)


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a MongoDB document to a JSON-safe dict.

    - ``_id`` (ObjectId) -> ``id`` (24-char hex string)
    - datetime values -> ISO-8601 strings
    - everything else passes through unchanged
    """
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            out["id"] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        else:
            out[key] = value
    return out


def serialize_many(docs) -> list[dict[str, Any]]:
    """Serialize an iterable of documents (e.g. a cursor)."""
    return [serialize_doc(d) for d in docs]
