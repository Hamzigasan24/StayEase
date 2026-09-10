"""MongoDB connection for StayEase (Step 7).

PostgreSQL keeps all structured/transactional data (users, hotels,
rooms, reservations, ...). MongoDB holds flexible documents:
reviews, notifications, activity_logs, search_history.

Collections are created automatically on first insert; indexes are
created idempotently by ``init_mongo_indexes`` (safe to run on every
startup — MongoDB ignores already-existing identical indexes).

Connection values come from the centralized settings (app/config.py).
"""

from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.database import Database

from app.config import settings

MONGODB_URL = settings.mongodb_url
MONGODB_DATABASE = settings.mongodb_database

# One shared client (thread-safe, pooled) for the whole application.
client: MongoClient = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
database: Database = client[MONGODB_DATABASE]


def get_database() -> Database:
    """Return the StayEase MongoDB database instance."""
    return database


def test_mongo_connection() -> dict:
    """Ping MongoDB. Returns server info or raises on failure."""
    info = client.server_info()  # forces a real connection.
    return {"version": info.get("version", "unknown")}


def init_mongo_indexes() -> dict:
    """Create collection indexes idempotently (name -> index names)."""
    db = get_database()
    created = {}
    created["reviews"] = db.reviews.create_indexes(
        [
            IndexModel([("hotel_id", ASCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("reservation_id", ASCENDING)]),
        ]
    )
    created["notifications"] = db.notifications.create_indexes(
        [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])]
    )
    created["activity_logs"] = db.activity_logs.create_indexes(
        [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])]
    )
    created["search_history"] = db.search_history.create_indexes(
        [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])]
    )
    return created
