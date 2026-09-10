"""Health endpoints (Step 14, public).

GET /health         — liveness: the process is running (no dependencies).
GET /health/ready   — readiness: PostgreSQL + MongoDB actually answer.

Readiness failures return 503 with the standard error envelope and
never expose connection strings, credentials, or tracebacks.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.postgres import engine
from app.utils.errors import error_body

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Liveness probe",
    description="Returns 200 when the API process is running. Checks nothing else.",
    responses={200: {"description": "Service is alive"}},
)
def liveness():
    """Process is up (always 200, no service checks)."""
    return {"success": True, "data": {"status": "healthy"}}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Returns 200 only when PostgreSQL and MongoDB both answer. "
    "Otherwise 503 with a generic SERVICE_UNAVAILABLE error.",
    responses={200: {"description": "Ready"}, 503: {"description": "A dependency is down"}},
)
def readiness():
    """Check required services; 503 when PostgreSQL or MongoDB is down."""
    services: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services["postgresql"] = "up"
    except Exception:
        services["postgresql"] = "down"
    try:
        from app.database.mongodb import test_mongo_connection

        test_mongo_connection()
        services["mongodb"] = "up"
    except Exception:
        services["mongodb"] = "down"
    if all(state == "up" for state in services.values()):
        return {"success": True, "data": {"status": "ready", "services": services}}
    return JSONResponse(
        status_code=503,
        content=error_body(
            "SERVICE_UNAVAILABLE",
            "One or more required services are unavailable",
            {"services": services},
        ),
    )
