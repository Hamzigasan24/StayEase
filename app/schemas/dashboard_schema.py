"""Pydantic schemas for the admin dashboard (Step 10, admin-only).

Money is carried as exact decimal STRINGS (e.g. "250000.00") so JSON
transport can never introduce float rounding — consistent with the
payment endpoints. Percentages are plain rounded floats.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserStats(BaseModel):
    total: int
    guests: int
    admins: int


class HotelSummary(BaseModel):
    total: int


class RoomSummary(BaseModel):
    total: int
    available: int
    occupied: int
    maintenance: int


class ReservationSummary(BaseModel):
    total: int
    pending: int
    confirmed: int
    checked_in: int
    checked_out: int
    cancelled: int


class PaymentSummary(BaseModel):
    total_paid: str
    pending: str
    refunded: str


class DashboardSummary(BaseModel):
    users: UserStats
    hotels: HotelSummary
    rooms: RoomSummary
    reservations: ReservationSummary
    payments: PaymentSummary


class ReservationStatistics(ReservationSummary):
    """Counts per status (same shape as the dashboard block)."""


class RoomStatistics(BaseModel):
    total_rooms: int
    available: int
    occupied: int
    maintenance: int
    occupancy_rate: float


class RevenueStatistics(BaseModel):
    total_paid: str
    pending_amount: str
    refunded_amount: str
    paid_transactions: int
    pending_transactions: int
    refunded_transactions: int


class MonthRevenue(BaseModel):
    month: int
    month_name: str
    revenue: str


class MonthlyRevenue(BaseModel):
    year: int
    months: list[MonthRevenue]


class RecentReservation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reservation_id: int
    guest_name: str | None
    hotel: str | None
    room_number: str | None
    check_in: str
    check_out: str
    total_amount: str | None
    status: str
    created_at: datetime


class RecentPayment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    reservation_id: int
    amount: str | None
    payment_method: str | None
    status: str
    transaction_reference: str | None
    paid_at: datetime | None
    created_at: datetime


class HotelStatistics(BaseModel):
    hotel_id: int
    hotel_name: str
    total_rooms: int
    available_rooms: int = 0
    occupied_rooms: int = 0
    maintenance_rooms: int = 0
    active_reservations: int | None = None
    occupancy_rate: float | None = None


class HotelsDashboard(BaseModel):
    hotels: list[HotelStatistics]


class OccupancyDashboard(BaseModel):
    total_rooms: int
    occupied_rooms: int
    available_rooms: int
    maintenance_rooms: int
    occupancy_rate: float
    hotels: list[HotelStatistics]


class ActivityEntry(BaseModel):
    id: str
    user_id: int | None
    action: str
    resource: str
    resource_id: int | None
    created_at: datetime


class ActivityDashboard(BaseModel):
    activities: list[ActivityEntry]
