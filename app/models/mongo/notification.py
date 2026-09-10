"""Notification document model (Step 7, MongoDB).

Document shape::

    {
        "_id": ObjectId,
        "user_id": int,        # PostgreSQL users.id (owner)
        "type": str,           # e.g. reservation_created, system, payment, ...
        "title": str,
        "message": str,
        "is_read": bool,
        "created_at": datetime,  # UTC
    }
"""

from datetime import datetime
from typing import Any

COLLECTION = "notifications"

NOTIFICATION_TYPES = (
    "reservation_created",
    "reservation_confirmed",
    "reservation_cancelled",
    "check_in",
    "check_out",
    "payment",
    "system",
)


def build_notification(
    user_id: int,
    type: str,
    title: str,
    message: str,
    created_at: datetime,
) -> dict[str, Any]:
    """Build an unread notification document for insertion."""
    return {
        "user_id": user_id,
        "type": type,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": created_at,
    }
