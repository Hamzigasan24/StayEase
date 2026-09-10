"""Pydantic schemas for payments (Step 8, simulated payments).

Clients send ONLY reservation_id + amount + payment_method.
status, transaction_reference, paid_at and created_at are
backend-controlled. No card numbers/CVV/OTPs exist anywhere.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination_schema import PaginationMetadata

PAYMENT_METHODS = ("cash", "card", "gcash", "bank_transfer")
PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded")


class PaymentCreate(BaseModel):
    """Body for POST /payments."""

    reservation_id: int
    amount: Decimal = Field(gt=0)
    payment_method: str


class PaymentResponse(BaseModel):
    """Payment as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    amount: Decimal | None
    payment_method: str | None
    status: str
    transaction_reference: str | None
    paid_at: datetime | None
    created_at: datetime


class ReservationPaymentHistory(BaseModel):
    """Balance summary + payment records for one reservation."""

    reservation_id: int
    total_amount: Decimal | None
    total_paid: Decimal
    remaining_balance: Decimal | None
    payments: list[PaymentResponse]


class PaymentListResponse(BaseModel):
    """Paginated payment results (guests see only their own)."""

    items: list[PaymentResponse]
    pagination: PaginationMetadata
