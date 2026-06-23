"""
Profile & account management routes.

- GET    /api/users/me        — get current user profile
- PUT    /api/users/me        — update profile (email)
- PUT    /api/users/me/password — change password
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.core.security import get_password_hash, verify_password
from app.models.user import UpdatePassword, User, UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# ═══════════════════════════════════════════════════════════════
#  Schemas
# ═══════════════════════════════════════════════════════════════


class UpdateProfileInput(BaseModel):
    """PUT /api/users/me"""

    email: str | None = None


# ═══════════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════════


@router.get("/me", response_model=UserPublic)
def get_profile(current_user: CurrentUser) -> User:
    """Get the current authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserPublic)
def update_profile(
    body: UpdateProfileInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> User:
    """Update profile fields (email)."""
    if current_user.id == 0:
        raise HTTPException(status_code=400, detail="管理员账号不支持修改个人资料")

    if body.email is not None:
        current_user.email = body.email

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.put("/me/password")
def change_password(
    body: UpdatePassword,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Change the current user's password."""
    if current_user.id == 0:
        raise HTTPException(status_code=400, detail="管理员账号不支持修改密码")

    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")

    current_user.password_hash = get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()

    return {"message": "密码已修改"}
