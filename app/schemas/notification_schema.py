"""Pydantic schemas for notifications (Step 7).

Regular users create notifications only for themselves (user_id is
accepted solely from admins); is_read/created_at are backend-controlled.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Body for POST /notifications."""

    user_id: int | None = Field(default=None, description="Admin-only: owner id.")
    type: str = Field(default="system")
    title: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=2000)


class NotificationResponse(BaseModel):
    """Notification as returned by the API."""

    id: str
    user_id: int
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
