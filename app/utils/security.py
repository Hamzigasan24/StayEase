"""Password hashing (Step 6).

Argon2id via pwdlib — modern, memory-hard, and the current OWASP
recommendation. (passlib+bcrypt was tried first but passlib 1.7.4 is
incompatible with bcrypt >= 4, so it cannot be used here.)
"""

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()  # Argon2id with safe defaults.


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage. Never store or log the input."""
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash (timing-safe)."""
    return _password_hash.verify(password, hashed_password)
