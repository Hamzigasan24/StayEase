"""Secure admin creation (Step 6, development helper).

Public registration can only create guests, so the first admin is made
here. Nothing is hard-coded: name/email come from flags or prompts,
the password is read securely with getpass (never echoed, never logged).

Usage (from the StayEase/ folder)::

    python scripts/create_admin.py --name "Ada Admin" --email ada@example.com
    # --password may be passed too, otherwise you are prompted securely.

Re-running for an existing email refuses to create a duplicate.
"""

import argparse
import getpass
import sys
from pathlib import Path

# Allow running as ``python scripts/create_admin.py`` from StayEase/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.security import hash_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a StayEase admin user.")
    parser.add_argument("--name", help="Admin display name (prompted if omitted).")
    parser.add_argument("--email", help="Admin email (prompted if omitted).")
    parser.add_argument("--password", help="Admin password (securely prompted if omitted).")
    args = parser.parse_args()

    name = args.name or input("Admin name: ").strip()
    email = args.email or input("Admin email: ").strip().lower()
    password = args.password or getpass.getpass("Admin password (min 8 chars): ")
    if not name or not email or len(password) < 8:
        print("Name, email and a password of at least 8 characters are required.")
        return 1

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first() is not None:
            print(f"User {email} already exists — refusing to create a duplicate.")
            return 1
        admin = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Admin created: id={admin.id} email={admin.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
