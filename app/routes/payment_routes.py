"""Payment endpoints (Steps 8 + 11, SIMULATED payments — no real gateway).

Guests act on their own reservations only; admins see/manage everything;
refunds are admin-only. Status changes happen exclusively through
process/refund — never from client input.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import payment_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.payment_schema import PaymentCreate, PaymentListResponse, PaymentResponse
from app.utils.auth import require_admin, require_guest

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending payment (simulated)",
    description="Backend assigns status='pending' and a unique transaction "
    "reference. Overpayment beyond the remaining balance returns 400. "
    "No real gateway; no card data is collected.",
    responses={201: {"description": "Payment created"}, 400: {"description": "Invalid amount/balance"}, 403: {"description": "Not your reservation"}},
)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Create a pending payment for your reservation (no overpayment)."""
    return payment_controller.create_payment(db, data, user)


@router.get("", response_model=PaymentListResponse)
def list_payments(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    status_filter: str | None = Query(default=None, alias="status"),
    payment_method: str | None = Query(default=None),
    reservation_id: int | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Search payments (own scope for guests) with paging + sorting."""
    items, pagination = payment_controller.get_payments(
        db, user, page, page_size, status_filter, payment_method,
        reservation_id, date_from, date_to, sort_by, sort_order,
    )
    return {"items": items, "pagination": pagination}


@router.get("/{payment_id}", response_model=PaymentResponse)
def read_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """One payment (own or admin; 404 when missing)."""
    return payment_controller.get_payment(db, payment_id, user)


@router.post(
    "/{payment_id}/process",
    response_model=PaymentResponse,
    summary="Simulate payment processing",
    description="pending → paid (+paid_at). Fully covering a pending "
    "reservation confirms it. Atomic; re-processing returns 400.",
    responses={200: {"description": "Payment processed"}, 400: {"description": "Wrong state"}},
)
def process_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_guest),
):
    """Simulate processing: pending -> paid (+paid_at, maybe confirms)."""
    return payment_controller.process_payment(db, payment_id, user)


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    summary="Simulated refund (admin-only)",
    description="paid → refunded; the record is kept for auditing.",
    responses={200: {"description": "Payment refunded"}, 400: {"description": "Not paid"}, 403: {"description": "Admin only"}},
)
def refund_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Simulated refund (admin-only): paid -> refunded, record kept."""
    return payment_controller.refund_payment(db, payment_id)
