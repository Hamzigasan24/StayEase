"""Pydantic schemas for activity logs (Step 7, read-only API).

Logs are written by the backend, never edited — so there is no
Update schema and no client-controlled Create schema beyond an
admin-only manual entry point.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityLogCreate(BaseModel):
    """Body for admin-only manual POST /activity-logs."""

    user_id: int | None = None
    action: str = Field(min_length=1, max_length=100)
    resource: str = Field(min_length=1, max_length=100)
    resource_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ActivityLogResponse(BaseModel):
    """Activity log entry as returned by the API."""

    id: str
    user_id: int | None
    action: str
    resource: str
    resource_id: int | None
    details: dict[str, Any]
    created_at: datetime
