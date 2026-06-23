"""
FastAPI dependencies — SQLModel-based auth & DB injection.

Aligns with full-stack-fastapi-template pattern:
  SessionDep    = Annotated[Session, Depends(get_db)]
  CurrentUser   = Annotated[User, Depends(get_current_user)]
  SuperUserDep  = Annotated[User, Depends(get_current_superuser)]
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import ALGORITHM
from app.models.user import TokenPayload, User

SessionDep = Annotated[Session, Depends(get_db)]

reusable_oauth2 = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    request: Request,
) -> str | None:
    """Extract JWT from Bearer header first, fallback to httpOnly cookie."""
    if credentials:
        return credentials.credentials
    # Cookie fallback — httpOnly 'token' cookie set by login/register
    return request.cookies.get("token")


def get_current_user(
    session: SessionDep,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(reusable_oauth2)],
) -> User:
    """Decode JWT → resolve User from DB.

    Supports both `Authorization: Bearer <token>` header and the httpOnly `token` cookie.
    Admin users (user_id=0, env-based) are returned as a light User object.
    Regular users are fetched from the `users` table via SQLModel.
    """
    token = _extract_token(credentials, request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的登录凭证",
        ) from None

    # Admin user (user_id=0 or sub="0", validated against .env)
    role = token_data.role or payload.get("role", "user")
    uid_str = token_data.sub or str(payload.get("user_id", ""))
    if role == "admin" and uid_str == "0":
        return User(
            id=0,
            username=payload.get("username", "admin"),
            role="admin",
            created_at="",
        )

    # Regular user — support both `sub` (template) and `user_id` (legacy) claims
    user_id_str: str | None = token_data.sub or payload.get("user_id")
    if user_id_str is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")
    user = session.get(User, int(user_id_str))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_superuser(current_user: CurrentUser) -> User:
    """Require admin role (env-based admin or DB superuser)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


SuperUserDep = Annotated[User, Depends(get_current_superuser)]
