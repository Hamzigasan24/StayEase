"""Shared pytest fixtures (Steps 12 + 14).

Isolation strategy (no production data touched):
- PostgreSQL: dedicated test database from settings (TEST_DATABASE_URL),
  schema created from the SQLAlchemy models (+ idempotent extras), all
  rows removed before AND after each test (fast TRUNCATE ... CASCADE).
- MongoDB: dedicated test database from settings (TEST_MONGO_DATABASE)
  on the same local server, collections dropped around each test.
- FastAPI dependency ``get_db`` is overridden to use the test database.
"""

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.database.mongodb as mongo_module
import app.models  # noqa: F401  (register all tables on Base.metadata)
from app.config import settings
from app.database.postgres import Base, get_db

TEST_PG_URL = settings.test_database_url
TEST_MONGO_DB = settings.test_mongo_database

_test_engine = create_engine(TEST_PG_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def _ensure_test_db_exists() -> None:
    """Create the test database on first run (uses the dev credentials)."""
    admin_url = TEST_PG_URL.rsplit("/", 1)[0] + "/stayease_db"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'stayease_test_db'")
        ).first()
        if not exists:
            conn.execute(text("CREATE DATABASE stayease_test_db OWNER stayease"))
    admin_engine.dispose()


_ensure_test_db_exists()
Base.metadata.create_all(_test_engine)
with _test_engine.begin() as conn:  # Step 9 idempotent extras.
    conn.execute(text("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ"))
    conn.execute(text("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS checked_out_at TIMESTAMPTZ"))

_real_mongo_db = mongo_module.database
_test_mongo_client = MongoClient(
    settings.mongodb_url, serverSelectionTimeoutMS=5000
)
_test_mongo_db = _test_mongo_client[TEST_MONGO_DB]
mongo_module.database = _test_mongo_db  # get_database() now serves the test DB.


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    import app.main as main_module

    main_module.app.dependency_overrides[get_db] = _override_get_db
    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        yield c
    main_module.app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_databases():
    """Empty every table/collection before AND after each test.

    Pre-cleaning makes runs self-healing when a previous process was
    killed mid-test (which would otherwise skip post-test cleanup).
    """
    _truncate_all()
    yield
    _truncate_all()


def _truncate_all():
    with _test_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, hotels, room_types, rooms, guests, "
                "reservations, payments RESTART IDENTITY CASCADE"
            )
        )
    for name in ("reviews", "notifications", "activity_logs", "search_history"):
        _test_mongo_db[name].delete_many({})
