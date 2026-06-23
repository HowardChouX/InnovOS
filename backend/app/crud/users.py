"""
User CRUD operations — SQLModel-based.

Aligns with full-stack-fastapi-template pattern:
  create_user()    — hash password, persist, return User
  get_user_by_username() — lookup by username
  authenticate()  — verify password with timing-attack prevention
"""

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRegister

# ── Constant-time dummy hash for user-not-found cases ──────────
# A bcrypt hash of a random password, used to prevent timing attacks
# by ensuring constant-time comparison even when username doesn't exist.
_DUMMY_HASH = "$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5GypGm9Gk1TzOyZvqJ7VxHXO"


def get_user_by_username(*, session: Session, username: str) -> User | None:
    """Look up a user by username."""
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def create_user(*, session: Session, user_in: UserRegister) -> User:
    """Create a new user with hashed password."""
    db_user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def authenticate(*, session: Session, username: str, password: str) -> User | None:
    """Verify credentials — constant-time comparison.

    Uses a dummy hash when the user is not found, preventing
    attackers from distinguishing "wrong password" from
    "user doesn't exist" via response timing.
    """
    db_user = get_user_by_username(session=session, username=username)
    if not db_user:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, db_user.password_hash):
        return None
    return db_user
