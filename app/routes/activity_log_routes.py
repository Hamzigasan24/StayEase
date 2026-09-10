"""Activity log endpoints (Step 7, admin-only, append-only).

Guests can neither write nor read audit entries — entries are produced
by the backend itself (login, registration, reservations, ...).
"""

from fastapi import APIRouter, Depends, Query, status

from app.controllers import activity_log_controller
from app.models.user import User
from app.schemas.activity_log_schema import ActivityLogCreate, ActivityLogResponse
from app.utils.auth import require_admin

router = APIRouter(prefix="/activity-logs", tags=["Activity Logs"])


@router.post("", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
def create_log_entry(
    data: ActivityLogCreate,
    user: User = Depends(require_admin),
):
    """Manually record an audit entry (admin-only)."""
    return activity_log_controller.create_log_entry(data)


@router.get("", response_model=list[ActivityLogResponse])
def list_log_entries(
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    user: User = Depends(require_admin),
):
    """Return audit entries, newest first (admin-only)."""
    return activity_log_controller.list_logs(user_id, action, limit)


@router.get("/{log_id}", response_model=ActivityLogResponse)
def read_log_entry(
    log_id: str,
    user: User = Depends(require_admin),
):
    """Return one audit entry (admin-only)."""
    return activity_log_controller.get_log(log_id)
