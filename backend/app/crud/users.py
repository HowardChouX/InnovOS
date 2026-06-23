"""
User CRUD operations — raw psycopg2 (SQLModel removed).
"""

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRegister

# ── Constant-time dummy hash for user-not-found cases ──────────
# A bcrypt hash of a random password, used to prevent timing attacks
# by ensuring constant-time comparison even when username doesn't exist.
_DUMMY_HASH = "$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5GypGm9Gk1TzOyZvqJ7VxHXO"


def get_user_by_username(*, db, username: str) -> User | None:
    """Look up a user by username."""
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return User(**row) if row else None


def create_user(*, db, user_in: UserRegister) -> User:
    """Create a new user with hashed password."""
    row = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id, username, password_hash, role, email, is_active, token_version, created_at",
        (user_in.username, get_password_hash(user_in.password)),
    ).fetchone()
    db.commit()
    return User(**row)


def authenticate(*, db, username: str, password: str) -> User | None:
    """Verify credentials — constant-time comparison.

    Uses a dummy hash when the user is not found, preventing
    attackers from distinguishing "wrong password" from
    "user doesn't exist" via response timing.
    """
    db_user = get_user_by_username(db=db, username=username)
    if not db_user:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, db_user.password_hash):
        return None
    return db_user
