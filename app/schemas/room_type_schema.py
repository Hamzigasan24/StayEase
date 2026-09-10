"""Pydantic schemas for room types (Step 4).

Money uses Decimal (matches Numeric in the database).
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pagination_schema import PaginationMetadata


class RoomTypeCreate(BaseModel):
    """Required fields for creating a room type."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    price_per_night: Decimal | None = Field(default=None, gt=0)
    capacity: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value.strip()


class RoomTypeUpdate(BaseModel):
    """All fields optional — only provided fields are updated."""

    model_config = ConfigDict(extra="forbid")  # id/created_at/etc. not settable.

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price_per_night: Decimal | None = Field(default=None, gt=0)
    capacity: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be empty")
        return value.strip() if value is not None else None


class RoomTypeResponse(BaseModel):
    """Room type data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price_per_night: Decimal | None
    capacity: int | None
    created_at: datetime


class RoomTypeListResponse(BaseModel):
    """Paginated room type search results."""

    items: list[RoomTypeResponse]
    pagination: PaginationMetadata
