"""Pydantic schemas for reviews (Step 7).

The author always comes from the JWT — clients never send user_id.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    """Body for POST /reviews."""

    hotel_id: int
    reservation_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewUpdate(BaseModel):
    """Body for PUT /reviews/{id} (rating and/or comment)."""

    model_config = ConfigDict(extra="forbid")

    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    """Review as returned by the API (id is the hex string of ObjectId)."""

    id: str
    user_id: int
    hotel_id: int
    reservation_id: int
    rating: int
    comment: str | None
    created_at: datetime
