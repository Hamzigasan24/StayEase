"""Pydantic schemas for guests (Step 4).

Note: no password_hash or other user credentials appear here —
guest responses expose profile fields only.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.pagination_schema import PaginationMetadata


def _blank_to_none(value: str | None) -> str | None:
    """Trim whitespace; meaningless empty strings become None (never stored)."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class GuestCreate(BaseModel):
    """Required fields for creating a guest profile."""

    user_id: int
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    identification_type: str | None = Field(default=None, max_length=50)
    identification_number: str | None = Field(default=None, max_length=100)

    @field_validator("phone", "address", "identification_type", "identification_number")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class GuestUpdate(BaseModel):
    """Updatable profile fields (user_id cannot be changed)."""

    model_config = ConfigDict(extra="forbid")  # user_id/id/etc. not settable.

    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    identification_type: str | None = Field(default=None, max_length=50)
    identification_number: str | None = Field(default=None, max_length=100)

    @field_validator("phone", "address", "identification_type", "identification_number")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class GuestResponse(BaseModel):
    """Guest data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    phone: str | None
    address: str | None
    identification_type: str | None
    identification_number: str | None
    created_at: datetime


class GuestListResponse(BaseModel):
    """Paginated guest search results (admin-only endpoint)."""

    items: list[GuestResponse]
    pagination: PaginationMetadata
