"""PostgreSQL connection for StayEase (Steps 2 + 14).

Connection values come from the centralized settings (app/config.py).
No hotel/room/reservation/payment/guest tables are created here.
Those models live in Step 3 using ``Base`` defined below.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _normalize_database_url(url: str) -> str:
    """Accept hosted Postgres URLs (Neon/Render/Supabase) as-is.

    Neon and Render give ``postgresql://...`` or ``postgres://...``.
    SQLAlchemy + psycopg3 needs ``postgresql+psycopg://...``.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


# Re-exported for backwards compatibility (import from app.config instead).
DATABASE_URL = _normalize_database_url(settings.database_url)

# Engine: manages the pool of connections to PostgreSQL.
# ``pool_pre_ping=True`` drops dead connections before use.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# SessionLocal: factory that creates a new database session per request.
# ``autocommit=False`` + ``autoflush=False`` = explicit, beginner-friendly commits.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: parent class for all Step 3 ORM models (Hotel, Room, ...).
# Example later: ``class Hotel(Base): __tablename__ = "hotels"``.
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a PostgreSQL session per request.

    Usage in Step 3+ routes::

        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.database.postgres import get_db

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Never leave the session in a failed transaction state.
        db.rollback()
        raise
    finally:
        db.close()
