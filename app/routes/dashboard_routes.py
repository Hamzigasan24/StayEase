"""Admin dashboard endpoints (Step 10, ALL admin-only).

Every route uses ``require_admin``: anonymous callers get 401,
signed-in guests get 403, admins get live statistics aggregated
in PostgreSQL (MongoDB only for the activity feed).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import dashboard_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.dashboard_schema import (
    ActivityDashboard,
    DashboardSummary,
    HotelsDashboard,
    MonthlyRevenue,
    OccupancyDashboard,
    RecentPayment,
    RecentReservation,
    ReservationStatistics,
    RevenueStatistics,
    RoomStatistics,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get(
    "",
    response_model=DashboardSummary,
    summary="Whole-system snapshot (admin-only)",
    description="Live aggregates: users, hotels, rooms, reservations per "
    "status, revenue (paid only). All numbers computed in PostgreSQL.",
    responses={200: {"description": "Dashboard snapshot"}, 403: {"description": "Admin only"}},
)
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Whole-system snapshot (users, hotels, rooms, reservations, payments)."""
    return dashboard_controller.get_summary(db)


@router.get("/reservations", response_model=ReservationStatistics)
def dashboard_reservations(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Reservation counts per status."""
    return dashboard_controller.get_reservation_stats(db)


@router.get("/rooms", response_model=RoomStatistics)
def dashboard_rooms(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Room totals + occupancy rate."""
    return dashboard_controller.get_room_stats(db)


@router.get("/revenue", response_model=RevenueStatistics)
def dashboard_revenue(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Revenue: only 'paid' counts (refunded tracked separately)."""
    return dashboard_controller.get_revenue_stats(db)


@router.get("/occupancy", response_model=OccupancyDashboard)
def dashboard_occupancy(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Global + per-hotel occupancy."""
    return dashboard_controller.get_occupancy(db)


@router.get("/recent-reservations", response_model=list[RecentReservation])
def dashboard_recent_reservations(
    limit: int = Query(default=10),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Newest reservations first (limit 1..100, else 400)."""
    return dashboard_controller.get_recent_reservations(db, limit)


@router.get("/recent-payments", response_model=list[RecentPayment])
def dashboard_recent_payments(
    limit: int = Query(default=10),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Newest payments first (limit 1..100, else 400)."""
    return dashboard_controller.get_recent_payments(db, limit)


@router.get("/monthly-revenue", response_model=MonthlyRevenue)
def dashboard_monthly_revenue(
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Paid revenue per month (default: current year; else 400)."""
    return dashboard_controller.get_monthly_revenue(db, year)


@router.get("/hotels", response_model=HotelsDashboard)
def dashboard_hotels(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Per-hotel rooms, active reservations and occupancy."""
    return dashboard_controller.get_hotels_dashboard(db)


@router.get("/activity", response_model=ActivityDashboard)
def dashboard_activity(
    limit: int = Query(default=10),
    user: User = Depends(require_admin),
):
    """Recent MongoDB activity entries (limit 1..100, else 400)."""
    return dashboard_controller.get_activity(limit)
