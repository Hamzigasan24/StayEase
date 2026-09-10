"""Pydantic schemas for rooms (Step 4)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pagination_schema import PaginationMetadata

ROOM_STATUSES = {"available", "occupied", "maintenance", "reserved"}


def _validate_status(value: str | None) -> str | None:
    """Accept only known statuses (None passes through for updates)."""
    if value is not None and value not in ROOM_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(ROOM_STATUSES))}")
    return value


class RoomCreate(BaseModel):
    """Required fields for creating a room."""

    hotel_id: int
    room_type_id: int
    room_number: str = Field(min_length=1, max_length=20)
    floor: int | None = Field(default=None, ge=0)
    status: str = Field(default="available")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _validate_status(value)  # type: ignore[return-value]

    @field_validator("room_number")
    @classmethod
    def _number_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("room_number must not be empty")
        return cleaned


class RoomUpdate(BaseModel):
    """All fields optional — only provided fields are updated."""

    model_config = ConfigDict(extra="forbid")  # id/created_at/etc. not settable.

    hotel_id: int | None = None
    room_type_id: int | None = None
    room_number: str | None = Field(default=None, min_length=1, max_length=20)
    floor: int | None = Field(default=None, ge=0)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return _validate_status(value)

    @field_validator("room_number")
    @classmethod
    def _number_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("room_number must not be empty")
        return cleaned


class RoomResponse(BaseModel):
    """Room data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    room_type_id: int
    room_number: str
    floor: int | None
    status: str
    created_at: datetime


class RoomListResponse(BaseModel):
    """Paginated room search results."""

    items: list[RoomResponse]
    pagination: PaginationMetadata


class AvailableRoomItem(BaseModel):
    """Enriched availability hit (room + hotel/type names + price)."""

    room_id: int
    room_number: str
    hotel_id: int
    hotel_name: str | None
    room_type_id: int
    room_type_name: str | None
    price_per_night: Decimal | None
    capacity: int | None
    status: str


class AvailableRoomListResponse(BaseModel):
    """Paginated availability search results."""

    items: list[AvailableRoomItem]
    pagination: PaginationMetadata
