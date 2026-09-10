"""Development-only database initializer (Steps 3 + 9).

Creates the 7 StayEase tables from the SQLAlchemy models.
Safe to re-run: ``create_all`` only issues CREATE TABLE for tables
that do not exist yet. It NEVER drops tables or deletes data.

No migration tooling (Alembic) is configured in this project, so the
Step 9 lifecycle columns are added with the smallest safe change:
``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` (a no-op when present,
data-preserving always). See ``ensure_step9_columns``.

Run explicitly from the ``StayEase/`` folder::

    python -m app.database.init_db
"""

from sqlalchemy import text

from app.database.postgres import Base, engine

# Import the models package so every model class registers itself
# on ``Base.metadata`` before ``create_all`` runs.
import app.models  # noqa: F401


def init_db() -> None:
    """Create all missing tables (never drops anything)."""
    Base.metadata.create_all(engine)
    ensure_step9_columns()
    ensure_dashboard_indexes()


def ensure_dashboard_indexes() -> None:
    """Add Step 10 dashboard indexes if missing (idempotent).

    Status/FK indexes already exist via the Step 3 models (index=True);
    only the missing date + payment-method indexes are created here.
    IF NOT EXISTS guarantees re-runs never create duplicates or fail.
    (rooms.room_number is covered by the uq_rooms_hotel_room_number
    composite unique index, so no extra index is added for it.)
    """
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_reservations_created_at "
        "ON reservations (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_reservations_check_in "
        "ON reservations (check_in)",
        "CREATE INDEX IF NOT EXISTS ix_reservations_check_out "
        "ON reservations (check_out)",
        "CREATE INDEX IF NOT EXISTS ix_payments_paid_at "
        "ON payments (paid_at)",
        "CREATE INDEX IF NOT EXISTS ix_payments_payment_method "
        "ON payments (payment_method)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def ensure_step9_columns() -> None:
    """Add Step 9 nullable lifecycle columns if missing (idempotent)."""
    statements = [
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS "
        "checked_in_at TIMESTAMPTZ",
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS "
        "checked_out_at TIMESTAMPTZ",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


if __name__ == "__main__":
    init_db()
    tables = sorted(Base.metadata.tables.keys())
    print(f"OK: {len(tables)} tables ready: {', '.join(tables)}")
