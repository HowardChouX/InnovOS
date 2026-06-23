"""
User models — SQLModel table + Pydantic API schemas.

Aligns with full-stack-fastapi-template pattern:
  User (table model) → UserPublic (response) → UserRegister/UserLogin (request)

Admin users are validated against .env vars (no DB record).
Regular users are stored in the `users` table.
"""

from sqlmodel import Field, SQLModel

# ═══════════════════════════════════════════════════════════════
#  Database model
# ═══════════════════════════════════════════════════════════════


class User(SQLModel, table=True):
    """SQLModel ORM for the `users` table."""

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=100)
    password_hash: str
    role: str = Field(default="user", max_length=20)
    email: str = Field(default="", max_length=255)
    is_active: int = Field(default=1)
    created_at: str | None = Field(default=None)


# ═══════════════════════════════════════════════════════════════
#  API request / response schemas
# ═══════════════════════════════════════════════════════════════


class UserRegister(SQLModel):
    """POST /api/auth/register"""

    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)


class UserLogin(SQLModel):
    """POST /api/auth/login"""

    username: str
    password: str


class UserPublic(SQLModel):
    """User data returned to client (never exposes password_hash)."""

    id: int
    username: str
    email: str = ""
    role: str
    created_at: str | None = None


class UserUpdate(SQLModel):
    """PATCH /api/users/{id} or /api/users/me"""

    email: str | None = None
    is_active: int | None = None


class UpdatePassword(SQLModel):
    """PATCH /api/users/me/password"""

    current_password: str
    new_password: str = Field(min_length=8)


class TokenPayload(SQLModel):
    """Contents of the JWT token (sub = user_id)."""

    sub: str | None = None
    role: str = "user"
