"""Pydantic schemas for search history (Step 7).

The searcher always comes from the JWT — clients never send user_id.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class SearchHistoryCreate(BaseModel):
    """Body for POST /search-history (all search fields optional)."""

    search_query: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    check_in: date | None = None
    check_out: date | None = None
    guests_count: int | None = Field(default=None, gt=0)


class SearchHistoryResponse(BaseModel):
    """Search history entry as returned by the API."""

    id: str
    user_id: int
    search_query: str | None
    city: str | None
    check_in: str | None
    check_out: str | None
    guests_count: int | None
    created_at: datetime
