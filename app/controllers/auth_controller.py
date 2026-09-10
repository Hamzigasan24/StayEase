"""Business logic for authentication (Step 6).

Registration always creates role='guest' (public users can never
self-promote to admin). Admins are created via scripts/create_admin.py.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.activity_log_controller import log_activity
from app.models.guest import Guest
from app.models.user import User
from app.schemas.auth_schema import UserLogin, UserRegister
from app.utils.auth import create_access_token
from app.utils.errors import email_exists, login_failed
from app.utils.security import hash_password, verify_password

def register_user(db: Session, data: UserRegister) -> User:
    """Create a guest account with a hashed password (409 on duplicate email).

    A matching Guest profile row is auto-created so the new user can
    book immediately without a separate profile step.
    """
    if db.query(User).filter(User.email == data.email).first() is not None:
        raise email_exists()
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="guest",  # forced: public registration can never choose admin.
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # race between the check above and the insert.
        db.rollback()
        raise email_exists()
    db.refresh(user)
    db.add(Guest(user_id=user.id))  # booking profile for the new account.
    db.commit()
    db.refresh(user)
    log_activity(user.id, "register", "auth", user.id, {"role": user.role})
    return user


def authenticate_user(db: Session, data: UserLogin) -> str:
    """Verify credentials and return a JWT, or 401 with a generic message.

    The message is deliberately vague so callers cannot probe which
    emails exist ("Invalid email or password" either way).
    """
    user = db.query(User).filter(User.email == data.email).first()
    if user is None or not verify_password(data.password, user.password_hash):
        log_activity(None, "login", "auth", None, {"success": False})
        raise login_failed()
    log_activity(user.id, "login", "auth", user.id, {"success": True})
    return create_access_token(user.id, user.role)
