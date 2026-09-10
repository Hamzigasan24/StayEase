"""MongoDB connection test endpoint (Step 7)."""

from fastapi import APIRouter, HTTPException, status

from app.database.mongodb import MONGODB_DATABASE, test_mongo_connection

router = APIRouter(prefix="/mongodb", tags=["MongoDB"])


@router.get("/test")
def test_mongodb():
    """Ping MongoDB. Never exposes the connection string or credentials."""
    try:
        test_mongo_connection()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not reachable",
        )
    return {"status": "connected", "database": MONGODB_DATABASE}
