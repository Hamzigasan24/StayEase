"""Review document model (Step 7, MongoDB).

A review references PostgreSQL rows by plain integer ids only —
MongoDB never duplicates the users/hotels/reservations tables.

Document shape::

    {
        "_id": ObjectId,
        "user_id": int,          # PostgreSQL users.id (author)
        "hotel_id": int,         # PostgreSQL hotels.id
        "reservation_id": int,   # PostgreSQL reservations.id
        "rating": int,           # 1..5
        "comment": str | None,
        "created_at": datetime,  # UTC
    }
"""

from datetime import datetime
from typing import Any

COLLECTION = "reviews"


def build_review(
    user_id: int,
    hotel_id: int,
    reservation_id: int,
    rating: int,
    comment: str | None,
    created_at: datetime,
) -> dict[str, Any]:
    """Build a review document for insertion."""
    return {
        "user_id": user_id,
        "hotel_id": hotel_id,
        "reservation_id": reservation_id,
        "rating": rating,
        "comment": comment,
        "created_at": created_at,
    }
