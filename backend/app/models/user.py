"""
User models — Pydantic BaseModel schemas (SQLModel removed).

Admin users are validated against .env vars (no DB record).
Regular users are stored in the `users` table.
"""

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════
#  Data model
# ═══════════════════════════════════════════════════════════════


class User(BaseModel):
    """User data model (not a DB table model — use raw SQL + psycopg2)."""

    id: int | None = None
    username: str
    password_hash: str
    role: str = "user"
    email: str = ""
    is_active: int = 1
    token_version: int = 0
    created_at: str | None = None


# ═══════════════════════════════════════════════════════════════
#  API request / response schemas
# ═══════════════════════════════════════════════════════════════


class UserRegister(BaseModel):
    """POST /api/auth/register"""

    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    """POST /api/auth/login"""

    username: str
    password: str


class UserPublic(BaseModel):
    """User data returned to client (never exposes password_hash)."""

    id: int
    username: str
    email: str = ""
    role: str
    created_at: str | None = None


class UserUpdate(BaseModel):
    """PATCH /api/users/{id} or /api/users/me"""

    email: str | None = None
    is_active: int | None = None


class UpdatePassword(BaseModel):
    """PATCH /api/users/me/password"""

    current_password: str
    new_password: str = Field(min_length=8)


class TokenPayload(BaseModel):
    """Contents of the JWT token (sub = user_id)."""

    sub: str | None = None
    role: str = "user"
    token_version: int = 0
