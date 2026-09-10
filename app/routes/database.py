"""Step 2 database connection test route.

GET /database/test tries a lightweight ``SELECT 1`` against PostgreSQL.
Success and failure responses never include credentials or DATABASE_URL.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database.postgres import get_db

router = APIRouter(prefix="/database", tags=["database"])


@router.get("/test")
def test_database_connection(db: Session = Depends(get_db)):
    """Test the PostgreSQL connection.

    Returns ``{"status": "success", ...}`` when reachable,
    otherwise ``{"status": "error", ...}`` without leaking secrets.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "success",
            "message": "PostgreSQL connection successful",
        }
    except OperationalError:
        return {
            "status": "error",
            "message": "Could not connect to PostgreSQL. "
            "Check that PostgreSQL is running and .env DATABASE_URL is correct.",
        }
    except Exception:  # noqa: BLE001 - intentionally generic, no secrets leaked
        return {
            "status": "error",
            "message": "Database test failed due to an unexpected error.",
        }
