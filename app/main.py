from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("stayease")

from app.routes import (
    activity_log_routes,
    auth_routes,
    dashboard_routes,
    database,
    guest_routes,
    health_routes,
    hotel_routes,
    mongo_routes,
    notification_routes,
    payment_routes,
    reservation_routes,
    review_routes,
    room_routes,
    room_type_routes,
    search_history_routes,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Init MongoDB indexes idempotently; close clients on shutdown."""
    logger.info("StayEase starting up (env=%s, debug=%s)", settings.app_env, settings.debug)
    try:
        from app.database.mongodb import init_mongo_indexes

        init_mongo_indexes()
    except Exception:
        # The /mongodb/test endpoint reports MongoDB health instead.
        logger.warning("MongoDB index init skipped (server may be down)")
    yield
    logger.info("StayEase shutting down")
    try:  # Release pooled connections cleanly; never fail shutdown.
        from app.database.mongodb import client as mongo_client
        from app.database.postgres import engine as pg_engine

        mongo_client.close()
        pg_engine.dispose()
    except Exception:
        pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Minimal hardening headers; never touches auth or docs routes."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


app = FastAPI(
    title=settings.app_name,
    description="Hotel Reservation and Management System",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: explicit origins from settings only. Never ["*"] + credentials.
# Swagger (/docs) is same-origin, so it keeps working regardless.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """All HTTP errors -> standard envelope (preserves auth headers).

    Registered on Starlette's base class so router-level 404s (unknown
    paths) use the envelope too, not just in-route HTTPExceptions.
    """
    from app.utils.errors import APIError, code_for, error_body

    if isinstance(exc, APIError):
        body = error_body(exc.code, str(exc.detail), exc.details)
    else:
        body = error_body(code_for(exc.status_code), str(exc.detail))
    if exc.status_code >= 500:
        logger.error("HTTP %s on %s: %s", exc.status_code, request.url.path, exc.detail)
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic/query errors -> VALIDATION_ERROR with field details."""
    from app.utils.errors import error_body

    details = [
        {
            "field": ".".join(str(p) for p in err["loc"] if p != "body") or "request",
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Request validation failed", details),
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """DB errors -> generic 500 (real error only in server logs)."""
    from app.utils.errors import error_body

    logger.error("Database error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=error_body("DATABASE_ERROR", "A database error occurred"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last resort: never leak stack traces or internals to clients."""
    from app.utils.errors import error_body

    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_SERVER_ERROR", "An unexpected error occurred"),
    )

# Step 2: database connection test route (GET /database/test).
app.include_router(database.router)

# Step 14: health probes (GET /health, GET /health/ready).
app.include_router(health_routes.router)

# Step 4: CRUD routers (order matters only inside room_routes:
# /rooms/available is declared before /rooms/{room_id} there).
app.include_router(hotel_routes.router)
app.include_router(room_type_routes.router)
app.include_router(room_routes.router)
app.include_router(guest_routes.router)

# Step 5: reservation router (/reservations/available is declared before
# /reservations/{reservation_id} inside the router module).
app.include_router(reservation_routes.router)

# Step 6: authentication router (public register/login, JWT-protected /me).
app.include_router(auth_routes.router)

# Step 7: MongoDB routers (flexible data; PostgreSQL remains the system
# of record for users/hotels/rooms/reservations).
app.include_router(mongo_routes.router)
app.include_router(review_routes.router)
app.include_router(notification_routes.router)
app.include_router(activity_log_routes.router)
app.include_router(search_history_routes.router)

# Step 8: payment router (simulated payments; PostgreSQL source of truth).
app.include_router(payment_routes.router)

# Step 10: admin dashboard router (all endpoints require admin role).
app.include_router(dashboard_routes.router)


@app.get("/")
def read_root():
    return {
        "message": "Welcome to StayEase Hotel Reservation API",
        "status": "API is running",
    }
