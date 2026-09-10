"""Deployment/config tests (Step 14).

Covers: health probes, readiness shape, CORS behavior, settings
loading + production safety, DB/Mongo failure envelopes.
Uses the isolated test databases; never production credentials.
"""

import pytest

from app.config import get_settings, settings


def test_health_liveness(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": {"status": "healthy"}}


def test_health_ready_ok(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ready"
    assert body["data"]["services"] == {"postgresql": "up", "mongodb": "up"}


def test_health_ready_shape_on_failure(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fail_connect(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("conn refused"))

    monkeypatch.setattr("app.routes.health_routes.engine.connect", fail_connect)
    r = client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["details"]["services"]["postgresql"] == "down"
    assert "stayease" not in r.text.lower() and "secret" not in r.text.lower()


def test_config_loads_from_env(client):
    s = get_settings()
    assert s.app_env in ("development", "production", "testing")
    assert s.algorithm == "HS256"
    assert s.access_token_expire_minutes == 30
    assert len(s.secret_key) >= 32
    assert isinstance(s.cors_origins_list, list)


def test_config_rejects_weak_secret():
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="secret", DATABASE_URL="x")


def test_config_rejects_bad_env():
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="x" * 40, DATABASE_URL="x", APP_ENV="staging")


def test_production_debug_default():
    from app.config import Settings

    # Code default (not the local .env, which enables DEBUG for development).
    assert Settings.model_fields["debug"].default is False
    assert Settings.model_fields["app_env"].default == "development"


def test_cors_allows_configured_origin(client):
    origin = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:3000"
    r = client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_blocks_unknown_origin(client):
    r = client.options(
        "/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_db_failure_envelope(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fail(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("conn refused"))

    monkeypatch.setattr("app.routes.health_routes.engine.connect", fail)
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_mongo_failure_envelope(client, monkeypatch):
    import app.routes.mongo_routes as mongo_routes

    def fail():
        raise TimeoutError("no server")

    monkeypatch.setattr(mongo_routes, "test_mongo_connection", fail)
    r = client.get("/mongodb/test")
    assert r.status_code == 503
    assert "mongodb://" not in r.text.lower()


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" in paths and "/health/ready" in paths


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
