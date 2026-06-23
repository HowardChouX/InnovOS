"""
Authentication & authorization utilities.
"""

import hmac
"""
Authentication & authorization utilities.

PROVISIONAL — kept for backward compatibility with 25+ existing modules.
NEW code should import from app.api.deps (SessionDep, CurrentUser, etc.).

Admin: validated against .env vars on every login (no DB record).
Users: stored in DB with bcrypt password hashing via SQLModel.

Internal implementation migrated from raw psycopg2 to SQLModel (Phase 1).
Return type is kept as dict for backward compatibility.
"""

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.core.security import ALGORITHM
from app.models.user import User

SECRET_KEY: str = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    # Dual-claim support: both `user_id` (legacy) and `sub` (template-aligned)
    if "user_id" in data and "sub" not in to_encode:
        to_encode["sub"] = str(data["user_id"])
    elif "sub" in data and "user_id" not in to_encode:
        to_encode["user_id"] = int(data["sub"])
    token: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def set_token_cookie(response: Response, token: str) -> None:
    """Set JWT as httpOnly secure cookie."""
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )


def clear_token_cookie(response: Response) -> None:
    """Clear the token cookie (logout)."""
    response.set_cookie(key="token", value="", httponly=True, max_age=0, path="/")


def _verify_admin_credentials(username: str, password: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    admin_user = settings.FIRST_SUPERUSER or ""
    admin_pass = settings.FIRST_SUPERUSER_PASSWORD or ""
    # 常量时间比较防止时序攻击
    return (hmac.compare_digest(username, admin_user) and
            hmac.compare_digest(password, admin_pass))


def _user_to_dict(user: User) -> dict[str, Any]:
    """Convert SQLModel User to dict (backward compat return type)."""
    return {
        "id": user.id if user.id is not None else 0,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at or "",
        "email": user.email,
        "is_active": user.is_active,
    }


_security_optional = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_optional),
) -> dict[str, Any]:
    """获取当前登录用户。

    管理员：从 .env 验证，每次登录都实时校验，不存 DB。
    普通用户：从 DB 读取并验证（通过 SQLModel）。

    支持 `Authorization: Bearer <token>` 头和 httpOnly `token` cookie 两种方式。
    NOTE: 保持 dict 返回类型以兼容 25+ 现有模块。
    """
    token: str | None = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role", "user")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的令牌")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的令牌") from None

    # 管理员（user_id=0 表示来自 env 验证的管理员）
    if user_id == 0 and role == "admin":
        return {
            "id": 0,
            "username": payload.get("username", "admin"),
            "role": "admin",
            "created_at": "",
        }

    # 普通用户 — 使用 SQLModel（Phase 1 migration）
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        return _user_to_dict(user)


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
