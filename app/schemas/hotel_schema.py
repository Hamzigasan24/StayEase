"""Pydantic schemas for hotels (Step 4).

Create  -> what the client sends to POST /hotels.
Update  -> all fields optional for PUT /hotels/{hotel_id}.
Response -> what the API returns (never any sensitive fields).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pagination_schema import PaginationMetadata


class HotelCreate(BaseModel):
    """Required fields for creating a hotel."""

    name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    description: str | None = None
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("address", "city", "phone")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value is not None else None
        return cleaned or None


class HotelUpdate(BaseModel):
    """All fields optional — only provided fields are updated."""

    model_config = ConfigDict(extra="forbid")  # id/created_at/etc. not settable.

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    description: str | None = None
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("address", "city", "phone")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value is not None else None
        return cleaned or None


class HotelResponse(BaseModel):
    """Hotel data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str | None
    city: str | None
    description: str | None
    phone: str | None
    created_at: datetime


class HotelListItem(HotelResponse):
    """Hotel + efficiently aggregated room counts (one GROUP BY, no N+1)."""

    total_rooms: int = 0
    available_rooms: int = 0
    occupied_rooms: int = 0
    maintenance_rooms: int = 0


class HotelListResponse(BaseModel):
    """Paginated hotel search results."""

    items: list[HotelListItem]
    pagination: PaginationMetadata
