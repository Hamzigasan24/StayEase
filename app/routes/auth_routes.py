"""Auth endpoints (Step 6)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.controllers import auth_controller
from app.database.postgres import get_db
from app.models.user import User
from app.schemas.auth_schema import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a guest account",
    description="Public registration. Always creates role='guest' with an "
    "auto-created guest profile. Duplicate email returns 409.",
    responses={201: {"description": "Account created"}, 409: {"description": "Email already registered"}},
)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Register a new guest account (role is always 'guest')."""
    return auth_controller.register_user(db, data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and get a JWT",
    description="Returns a Bearer access token (30-minute expiry). Failures "
    "always return generic 401 'Invalid email or password'.",
    responses={200: {"description": "JWT issued"}, 401: {"description": "Bad credentials"}},
)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Log in and receive a JWT access token."""
    token = auth_controller.authenticate_user(db, data)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current authenticated user",
    description="Requires 'Authorization: Bearer <JWT>'. Returns 401 without a valid token.",
    responses={200: {"description": "Current user"}, 401: {"description": "Not authenticated"}},
)
def read_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user (requires JWT)."""
    return user
