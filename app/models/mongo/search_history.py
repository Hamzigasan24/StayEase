"""Search history document model (Step 7, MongoDB).

One row per availability search a user performs.

Document shape::

    {
        "_id": ObjectId,
        "user_id": int,          # PostgreSQL users.id (searcher)
        "search_query": str | None,
        "city": str | None,
        "check_in": str | None,  # ISO date, e.g. "2026-09-15"
        "check_out": str | None,
        "guests_count": int | None,
        "created_at": datetime,  # UTC
    }

Dates are stored as ISO strings (not BSON dates) so partial searches
(city-only, no dates) stay simple and JSON round-trips stay trivial.
"""

from datetime import datetime
from typing import Any

COLLECTION = "search_history"


def build_search_history(
    user_id: int,
    search_query: str | None,
    city: str | None,
    check_in: str | None,
    check_out: str | None,
    guests_count: int | None,
    created_at: datetime,
) -> dict[str, Any]:
    """Build a search history document for insertion."""
    return {
        "user_id": user_id,
        "search_query": search_query,
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "guests_count": guests_count,
        "created_at": created_at,
    }
