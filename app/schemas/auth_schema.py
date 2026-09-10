"""Pydantic schemas for authentication (Step 6).

Passwords appear ONLY in Register/Login request bodies — never in
responses, logs, or the database (only Argon2 hashes are stored).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Roles the system understands. Public registration always gets "guest".
VALID_ROLES = ("admin", "guest")


class UserRegister(BaseModel):
    """Public registration body. Note: NO role field on purpose —
    the backend forces role='guest' so nobody can self-promote."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # Trim + consistent lowercase so "User@X.com" and "user@x.com" collide.
        return value.strip().lower()


class UserLogin(BaseModel):
    """Login body."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    """Safe user info — never includes password or password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT returned by POST /auth/login."""

    access_token: str
    token_type: str = "bearer"
