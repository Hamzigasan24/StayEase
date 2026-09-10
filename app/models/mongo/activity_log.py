"""Activity log document model (Step 7, MongoDB).

Append-only audit trail, written by the backend when important actions
occur (login, registration, reservation create/cancel, ...).

Document shape::

    {
        "_id": ObjectId,
        "user_id": int | None,  # actor (None = anonymous/failed login)
        "action": str,          # e.g. "login", "create_reservation"
        "resource": str,        # e.g. "auth", "reservation"
        "resource_id": int | None,
        "details": dict,        # free-form JSON-safe extras
        "created_at": datetime,  # UTC
    }
"""

from datetime import datetime
from typing import Any

COLLECTION = "activity_logs"


def build_activity_log(
    user_id: int | None,
    action: str,
    resource: str,
    resource_id: int | None,
    details: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    """Build an activity log document for insertion (never updated)."""
    return {
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "details": details,
        "created_at": created_at,
    }
