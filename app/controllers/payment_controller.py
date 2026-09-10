"""Business logic for payments (Step 8, SIMULATED — no real gateway).

Money is always Decimal. PostgreSQL is the source of truth; MongoDB
only receives notifications + activity entries (no payment data copies
beyond ids/amount/method, never credentials — none are ever collected).
"""

import secrets
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.activity_log_controller import log_activity
from app.controllers.reservation_controller import get_reservation
from app.database.mongodb import get_database
from app.models.mongo.notification import build_notification
from app.models.guest import Guest
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.pagination_schema import PaginationMetadata
from app.schemas.payment_schema import PAYMENT_METHODS, PaymentCreate
from app.utils.mongo_helpers import utcnow
from app.utils.query_helpers import apply_sort, paginate, validate_page, validate_sort

PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded")

PAYMENT_SORT_FIELDS = {
    "created_at": Payment.created_at,
    "paid_at": Payment.paid_at,
    "amount": Payment.amount,
    "status": Payment.status,
}

def generate_transaction_reference() -> str:
    """STAY-YYYYMMDD-XXXXXX (date + 6 secure random chars, no PII)."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand = secrets.token_hex(3).upper()  # 6 hex chars.
    return f"STAY-{day}-{rand}"


def total_paid(db: Session, reservation_id: int) -> Decimal:
    """SUM of paid payments for a reservation (0 when none)."""
    value = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.reservation_id == reservation_id, Payment.status == "paid")
        .scalar()
    )
    return Decimal(value)


def remaining_balance(db: Session, reservation: Reservation) -> Decimal | None:
    """reservation.total - paid (None when the reservation has no total)."""
    if reservation.total_amount is None:
        return None
    return Decimal(reservation.total_amount) - total_paid(db, reservation.id)


def _check_owner(payment: Payment, user: User) -> None:
    """403 unless the caller owns the payment's reservation or is admin."""
    if user.role != "admin" and payment.reservation.guest.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this payment",
        )


def _notify(owner_id: int, title: str, message: str) -> None:
    """Best-effort MongoDB notification (never breaks the PG flow)."""
    try:
        get_database().notifications.insert_one(
            build_notification(
                user_id=owner_id,
                type="payment",
                title=title,
                message=message,
                created_at=utcnow(),
            )
        )
    except Exception:
        pass


def _unique_reference(db: Session) -> str:
    """Generate a transaction reference not already in use."""
    for _ in range(5):
        ref = generate_transaction_reference()
        if db.query(Payment).filter(Payment.transaction_reference == ref).first() is None:
            return ref
    return f"{generate_transaction_reference()}-{secrets.token_hex(2).upper()}"


def create_payment(db: Session, data: PaymentCreate, user: User) -> Payment:
    """Create a pending payment after all business validations."""
    reservation = get_reservation(db, data.reservation_id)  # 404.
    if user.role != "admin" and reservation.guest.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to pay for this reservation",
        )
    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot pay for a cancelled reservation",
        )
    if data.payment_method not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"payment_method must be one of: {', '.join(PAYMENT_METHODS)}",
        )
    if reservation.total_amount is not None:
        left = remaining_balance(db, reservation)
        if data.amount > left:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment exceeds remaining balance of {left}",
            )
    payment = Payment(
        reservation_id=reservation.id,
        amount=data.amount,
        payment_method=data.payment_method,
        status="pending",
        transaction_reference=_unique_reference(db),
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create payment",
        )
    db.refresh(payment)
    owner_id = reservation.guest.user_id
    _notify(owner_id, "Payment Pending",
            f"Payment {payment.transaction_reference} for reservation #{reservation.id} is pending.")
    log_activity(owner_id, "payment_created", "payment", payment.id,
                 {"reservation_id": reservation.id, "amount": str(payment.amount),
                  "payment_method": payment.payment_method})
    return payment


def get_payments(
    db: Session,
    user: User,
    page: int = 1,
    page_size: int = 10,
    status_filter: str | None = None,
    payment_method: str | None = None,
    reservation_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[Payment], PaginationMetadata]:
    """Filter/sort/paginate payments (all DB-side; guests see only own)."""
    page, page_size = validate_page(page, page_size)
    column, descending = validate_sort(sort_by, sort_order, PAYMENT_SORT_FIELDS)
    if status_filter is not None and status_filter not in PAYMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(PAYMENT_STATUSES)}",
        )
    if payment_method is not None and payment_method not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"payment_method must be one of: {', '.join(PAYMENT_METHODS)}",
        )
    query = db.query(Payment).order_by(Payment.id)
    if user.role != "admin":
        query = (
            query.join(Reservation, Payment.reservation_id == Reservation.id)
            .join(Guest, Reservation.guest_id == Guest.id)
            .filter(Guest.user_id == user.id)
        )
    if status_filter is not None:
        query = query.filter(Payment.status == status_filter)
    if payment_method is not None:
        query = query.filter(Payment.payment_method == payment_method)
    if reservation_id is not None:
        if user.role != "admin":
            res = db.get(Reservation, reservation_id)
            if res is None or res.guest.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view these payments",
                )
        query = query.filter(Payment.reservation_id == reservation_id)
    if date_from is not None:
        query = query.filter(Payment.created_at >= date_from)
    if date_to is not None:
        query = query.filter(Payment.created_at <= date_to)
    query = apply_sort(query, column, descending, default=Payment.id.desc())
    return paginate(query, page, page_size)


def get_payment(db: Session, payment_id: int, user: User) -> Payment:
    """One payment (own or admin)."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )
    _check_owner(payment, user)
    return payment


def get_reservation_history(db: Session, reservation_id: int, user: User) -> dict:
    """Balance summary + records for one reservation (own or admin)."""
    reservation = get_reservation(db, reservation_id)  # 404.
    if user.role != "admin" and reservation.guest.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this reservation's payments",
        )
    payments = (
        db.query(Payment)
        .filter(Payment.reservation_id == reservation.id)
        .order_by(Payment.id)
        .all()
    )
    paid = total_paid(db, reservation.id)
    total = Decimal(reservation.total_amount) if reservation.total_amount is not None else None
    return {
        "reservation_id": reservation.id,
        "total_amount": total,
        "total_paid": paid,
        "remaining_balance": (total - paid) if total is not None else None,
        "payments": payments,
    }


def process_payment(db: Session, payment_id: int, user: User) -> Payment:
    """Simulate processing: pending -> paid, stamp paid_at, maybe confirm.

    All PG writes commit atomically; any failure rolls everything back.
    """
    payment = get_payment(db, payment_id, user)  # 404/403.
    if payment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only pending payments can be processed (current: {payment.status})",
        )
    reservation = payment.reservation
    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot process payment for a cancelled reservation",
        )
    try:
        payment.status = "paid"
        payment.paid_at = datetime.now(timezone.utc)
        db.flush()
        # Confirm a pending reservation once fully covered.
        if (
            reservation.status == "pending"
            and reservation.total_amount is not None
            and total_paid(db, reservation.id) >= Decimal(reservation.total_amount)
        ):
            reservation.status = "confirmed"
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process payment",
        )
    db.refresh(payment)
    owner_id = reservation.guest.user_id
    _notify(owner_id, "Payment Successful",
            f"Your payment for reservation #{reservation.id} was successfully processed.")
    log_activity(owner_id, "payment_processed", "payment", payment.id,
                 {"reservation_id": reservation.id, "amount": str(payment.amount),
                  "payment_method": payment.payment_method})
    return payment


def refund_payment(db: Session, payment_id: int) -> Payment:
    """Admin-only simulated refund: paid -> refunded, record kept.

    A confirmed reservation that drops below full coverage returns to
    pending; cancelled/checked-in/checked-out reservations are untouched.
    """
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )
    if payment.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only paid payments can be refunded (current: {payment.status})",
        )
    reservation = payment.reservation
    try:
        payment.status = "refunded"
        payment.paid_at = None
        db.flush()
        if (
            reservation.status == "confirmed"
            and reservation.total_amount is not None
            and total_paid(db, reservation.id) < Decimal(reservation.total_amount)
        ):
            reservation.status = "pending"
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not refund payment",
        )
    db.refresh(payment)
    owner_id = reservation.guest.user_id
    _notify(owner_id, "Payment Refunded",
            f"Your payment for reservation #{reservation.id} has been refunded.")
    log_activity(owner_id, "payment_refunded", "payment", payment.id,
                 {"reservation_id": reservation.id, "amount": str(payment.amount)})
    return payment
