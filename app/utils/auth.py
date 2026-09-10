"""JWT creation/verification plus auth dependencies (Step 6).

Flow: client sends ``Authorization: Bearer <JWT>`` -> ``get_current_user``
decodes it (401 on missing/invalid/expired/malformed) and loads the user
from PostgreSQL. ``require_admin`` adds a 403 role check on top.
``require_guest`` marks booking-level routes usable by any signed-in user
(guests act for themselves; admins may act for anyone).
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database.postgres import get_db
from app.models.user import User

# Re-exported for backwards compatibility (import from app.config instead).
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# HTTP Bearer scheme: Swagger shows an "Authorize" button for pasting the JWT.
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, role: str) -> str:
    """Mint a JWT with sub (user id), role and expiry, signed by SECRET_KEY."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    """401 with a WWW-Authenticate header (no sensitive details)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user or raise 401.

    Handles: missing token, malformed/invalid token, expired token,
    and tokens whose user no longer exists. Never reveals which
    credential part was wrong beyond the generic message.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError):
        raise _unauthorized("Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid or expired token")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of 401.

    Used by public endpoints (e.g. room search) that personalize
    or log for signed-in callers without requiring login.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError):
        return None
    return db.get(User, user_id)


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only admins (403 for authenticated non-admins)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_guest(user: User = Depends(get_current_user)) -> User:
    """Allow any signed-in user on booking-level routes.

    Guests act for themselves; admins may additionally act for others
    (controllers branch on ``user.role``). Anonymous callers get 401
    from ``get_current_user`` before reaching here.
    """
    return user
