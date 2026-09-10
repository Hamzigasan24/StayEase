"""Admin dashboard business logic (Step 10, admin-only).

Every number is aggregated in PostgreSQL (COUNT/SUM/GROUP BY) — rows
are never pulled into Python just to be counted. Money stays Decimal
until the final ``str()`` for JSON; percentages are rounded floats
with zero-division guards. Activity comes from MongoDB (Step 7).
"""

import calendar
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.database.mongodb import get_database
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.user import User
from app.utils.mongo_helpers import serialize_many

ACTIVE_RESERVATION_STATUSES = ("pending", "confirmed", "checked_in")


def _money(value) -> str:
    """Exact decimal string for JSON (None -> '0.00' where a sum is expected)."""
    return str(Decimal(value) if value is not None else Decimal("0"))


def _rate(part: int, whole: int) -> float:
    """Percentage rounded to 2 decimals; 0 when there is nothing to divide."""
    return round(part / whole * 100, 2) if whole else 0.0


def _count_by_status(db: Session) -> dict[str, int]:
    """One query: reservation counts per status (+ total)."""
    rows = (
        db.query(Reservation.status, func.count(Reservation.id))
        .group_by(Reservation.status)
        .all()
    )
    counts = {s: 0 for s in ("pending", "confirmed", "checked_in", "checked_out", "cancelled")}
    for state, num in rows:
        counts[state] = num
    counts["total"] = sum(counts.values())
    return counts


def _room_breakdown(db: Session, hotel_id: int | None = None) -> dict[str, int]:
    """Room counts per status, optionally for one hotel."""
    query = db.query(Room.status, func.count(Room.id)).group_by(Room.status)
    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)
    counts = {"available": 0, "occupied": 0, "maintenance": 0, "reserved": 0}
    for state, num in query.all():
        counts[state] = counts.get(state, 0) + num
    counts["total"] = sum(counts.values())
    return counts


def _payment_sums(db: Session) -> dict:
    """SUM + COUNT per payment status in a single aggregation."""
    rows = (
        db.query(
            Payment.status,
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0),
        )
        .group_by(Payment.status)
        .all()
    )
    out = {s: {"n": 0, "sum": Decimal("0")} for s in ("paid", "pending", "failed", "refunded")}
    for state, num, total in rows:
        out[state] = {"n": num, "sum": Decimal(total)}
    return out


def get_summary(db: Session) -> dict:
    """Whole-system snapshot for GET /admin/dashboard."""
    users_total = db.query(func.count(User.id)).scalar()
    admins = db.query(func.count(User.id)).filter(User.role == "admin").scalar()
    rooms = _room_breakdown(db)
    res = _count_by_status(db)
    pay = _payment_sums(db)
    return {
        "users": {"total": users_total, "guests": users_total - admins, "admins": admins},
        "hotels": {"total": db.query(func.count(Hotel.id)).scalar()},
        "rooms": {
            "total": rooms["total"], "available": rooms["available"],
            "occupied": rooms["occupied"], "maintenance": rooms["maintenance"],
        },
        "reservations": res,
        "payments": {
            "total_paid": _money(pay["paid"]["sum"]),
            "pending": _money(pay["pending"]["sum"]),
            "refunded": _money(pay["refunded"]["sum"]),
        },
    }


def get_reservation_stats(db: Session) -> dict:
    """Counts per reservation status."""
    return _count_by_status(db)


def get_room_stats(db: Session) -> dict:
    """Room totals + occupancy rate."""
    rooms = _room_breakdown(db)
    return {
        "total_rooms": rooms["total"],
        "available": rooms["available"],
        "occupied": rooms["occupied"],
        "maintenance": rooms["maintenance"],
        "occupancy_rate": _rate(rooms["occupied"], rooms["total"]),
    }


def get_revenue_stats(db: Session) -> dict:
    """Revenue rule: ONLY status='paid' counts as revenue.

    Refunded = money returned (tracked separately, not revenue).
    Pending/failed never count as revenue.
    """
    pay = _payment_sums(db)
    return {
        "total_paid": _money(pay["paid"]["sum"]),
        "pending_amount": _money(pay["pending"]["sum"]),
        "refunded_amount": _money(pay["refunded"]["sum"]),
        "paid_transactions": pay["paid"]["n"],
        "pending_transactions": pay["pending"]["n"],
        "refunded_transactions": pay["refunded"]["n"],
    }


def get_monthly_revenue(db: Session, year: int | None) -> dict:
    """Paid revenue grouped by month (paid_at). Year defaults to this year."""
    if year is None:
        year = datetime.now().year
    if not 2000 <= year <= 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year must be between 2000 and 2100",
        )
    rows = (
        db.query(
            extract("month", Payment.paid_at).label("month"),
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .filter(
            Payment.status == "paid",
            Payment.paid_at.is_not(None),
            extract("year", Payment.paid_at) == year,
        )
        .group_by("month")
        .all()
    )
    by_month = {int(m): Decimal(total) for m, total in rows}
    return {
        "year": year,
        "months": [
            {"month": m, "month_name": calendar.month_name[m],
             "revenue": _money(by_month.get(m, Decimal("0")))}
            for m in range(1, 13)
        ],
    }


def _check_limit(limit: int) -> int:
    """Shared 1..100 bound for 'recent' endpoints (400, not 422)."""
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 100",
        )
    return limit


def get_recent_reservations(db: Session, limit: int) -> list[dict]:
    """Newest reservations with guest/hotel/room names (no sensitive data)."""
    limit = _check_limit(limit)
    rows = (
        db.query(Reservation, User.name, Hotel.name, Room.room_number)
        .join(Guest, Reservation.guest_id == Guest.id)
        .join(User, Guest.user_id == User.id)
        .join(Hotel, Reservation.hotel_id == Hotel.id)
        .join(Room, Reservation.room_id == Room.id)
        .order_by(Reservation.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "reservation_id": res.id,
            "guest_name": uname,
            "hotel": hname,
            "room_number": rnum,
            "check_in": res.check_in.isoformat(),
            "check_out": res.check_out.isoformat(),
            "total_amount": str(res.total_amount) if res.total_amount is not None else None,
            "status": res.status,
            "created_at": res.created_at,
        }
        for res, uname, hname, rnum in rows
    ]


def get_recent_payments(db: Session, limit: int) -> list[dict]:
    """Newest payments (method/amount/reference only — no credentials exist)."""
    limit = _check_limit(limit)
    payments = (
        db.query(Payment).order_by(Payment.id.desc()).limit(limit).all()
    )
    return [
        {
            "payment_id": p.id,
            "reservation_id": p.reservation_id,
            "amount": str(p.amount) if p.amount is not None else None,
            "payment_method": p.payment_method,
            "status": p.status,
            "transaction_reference": p.transaction_reference,
            "paid_at": p.paid_at,
            "created_at": p.created_at,
        }
        for p in payments
    ]


def get_hotels_dashboard(db: Session) -> dict:
    """Per-hotel rooms breakdown + active reservations + occupancy."""
    hotels = db.query(Hotel).order_by(Hotel.id).all()
    active = dict(
        db.query(Reservation.hotel_id, func.count(Reservation.id))
        .filter(Reservation.status.in_(ACTIVE_RESERVATION_STATUSES))
        .group_by(Reservation.hotel_id)
        .all()
    )
    out = []
    for hotel in hotels:
        rooms = _room_breakdown(db, hotel.id)
        out.append({
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "total_rooms": rooms["total"],
            "available_rooms": rooms["available"],
            "occupied_rooms": rooms["occupied"],
            "maintenance_rooms": rooms["maintenance"],
            "active_reservations": active.get(hotel.id, 0),
            "occupancy_rate": _rate(rooms["occupied"], rooms["total"]),
        })
    return {"hotels": out}


def get_occupancy(db: Session) -> dict:
    """Global occupancy + per-hotel breakdown."""
    rooms = _room_breakdown(db)
    hotels = get_hotels_dashboard(db)["hotels"]
    return {
        "total_rooms": rooms["total"],
        "occupied_rooms": rooms["occupied"],
        "available_rooms": rooms["available"],
        "maintenance_rooms": rooms["maintenance"],
        "occupancy_rate": _rate(rooms["occupied"], rooms["total"]),
        "hotels": [
            {
                "hotel_id": h["hotel_id"],
                "hotel_name": h["hotel_name"],
                "total_rooms": h["total_rooms"],
                "occupied_rooms": h["occupied_rooms"],
                "occupancy_rate": h["occupancy_rate"],
            }
            for h in hotels
        ],
    }


def get_activity(limit: int) -> dict:
    """Recent MongoDB activity entries, newest first (admin-only)."""
    _check_limit(limit)
    try:
        docs = list(
            get_database().activity_logs.find().sort("created_at", -1).limit(limit)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Activity store is not reachable",
        )
    return {"activities": serialize_many(docs)}
