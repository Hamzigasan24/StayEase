"""Centralized application settings (Step 14).

Single source of truth for every environment-driven value. Previously
``load_dotenv`` + ``os.getenv`` were duplicated in three modules; now
everything reads ``settings`` from here.

Values come from the process environment with ``StayEase/.env`` as a
fallback (never commit real secrets — see ``.env.example``).

Production safety:
- ``SECRET_KEY`` has NO default: importing without it fails fast with a
  clear configuration error instead of silently running insecure.
- ``DEBUG`` defaults to False; production must keep it False so error
  responses stay generic.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tunable values with safe types and defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application.
    app_name: str = Field(default="StayEase Hotel Reservation API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # PostgreSQL (SQLAlchemy). No default on purpose: fail fast if unset.
    database_url: str = Field(alias="DATABASE_URL")

    # MongoDB (PyMongo).
    mongodb_url: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URL")
    mongodb_database: str = Field(default="stayease_db", alias="MONGODB_DATABASE")

    # JWT. No default: missing SECRET_KEY must never run insecure.
    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # CORS (comma-separated origins, e.g. "http://localhost:3000,...").
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # Testing (used by tests/conftest.py; never production data).
    test_database_url: str = Field(
        default="postgresql+psycopg://stayease:stayease123@localhost:5432/stayease_test_db",
        alias="TEST_DATABASE_URL",
    )
    test_mongo_database: str = Field(default="stayease_test", alias="TEST_MONGO_DATABASE")

    @field_validator("app_env")
    @classmethod
    def _env_known(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ("development", "production", "testing"):
            raise ValueError("APP_ENV must be development, production or testing")
        return value

    @field_validator("secret_key")
    @classmethod
    def _secret_strong(cls, value: str) -> str:
        weak = {"secret", "123456", "password", "changeme", "stayease-secret"}
        if len(value.strip()) < 32 or value.strip().lower() in weak:
            raise ValueError("SECRET_KEY must be a strong random value of at least 32 characters")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed origins; empty list means 'no browser cross-origin access'."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise RuntimeError(
            "Invalid application configuration. Check the .env file "
            "(see .env.example). Details are logged, never returned to clients."
        ) from exc


@lru_cache
def get_settings() -> Settings:
    """Cached singleton (override in tests via get_settings.cache_clear())."""
    return _load_settings()


settings = get_settings()
