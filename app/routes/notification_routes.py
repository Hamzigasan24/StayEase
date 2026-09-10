"""Notification endpoints (Step 7)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.notification_schema import NotificationCreate, NotificationResponse
from app.utils.auth import require_guest

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED
)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Create a notification (for yourself; admins may target any user)."""
    return notification_controller.create_notification(db, data, user)


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = Query(default=False),
    user: User = Depends(require_guest),
):
    """Your notifications, newest first (admins see all)."""
    return notification_controller.list_notifications(user, unread_only)


@router.get("/{notification_id}", response_model=NotificationResponse)
def read_notification(
    notification_id: str,
    user: User = Depends(require_guest),
):
    """One notification (own or admin)."""
    return notification_controller.get_notification(notification_id, user)


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    user: User = Depends(require_guest),
):
    """Mark a notification as read (own or admin)."""
    return notification_controller.mark_read(notification_id, user)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_notification(
    notification_id: str,
    user: User = Depends(require_guest),
):
    """Delete a notification (own or admin)."""
    notification_controller.delete_notification(notification_id, user)
    return None
