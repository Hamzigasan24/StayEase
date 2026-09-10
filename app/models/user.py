"""User account model (Step 3).

One login account per person. A user with role "guest" can have
exactly one matching row in the ``guests`` table (one-to-one).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.postgres import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' used as the default for ``created_at``."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="guest")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # One-to-one: one user -> at most one guest profile.
    # Deleting a user also deletes its guest profile (and nothing else).
    guest: Mapped["Guest | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
    )
