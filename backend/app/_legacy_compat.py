"""旧认证实现的兼容垫片。

仅供过渡期使用，新代码请用 app.auth.instance 的 current_active_user/current_superuser。
"""
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.user import User

ACCESS_TOKEN_EXPIRE_HOURS = 24

SECRET_KEY: str = settings.SECRET_KEY
ALGORITHM = "HS256"

_security_optional = HTTPBearer(auto_error=False)


def create_access_token(data: dict[str, Any]) -> str:
    """兼容旧 API：签发 JWT。"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    if "user_id" in data and "sub" not in to_encode:
        to_encode["sub"] = str(data["user_id"])
    elif "sub" in data and "user_id" not in to_encode:
        to_encode["user_id"] = int(data["sub"])
    token: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def set_token_cookie(response: Response, token: str) -> None:
    """兼容旧 API：设置 __Host-token cookie。"""
    response.set_cookie(
        key="__Host-token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )


def clear_token_cookie(response: Response) -> None:
    """兼容旧 API：清除 token cookie。"""
    response.set_cookie(
        key="__Host-token", value="", httponly=True, secure=True,
        max_age=0, path="/",
    )


def _verify_admin_credentials(username: str, password: str) -> bool:
    """兼容旧 API：常量时间比较管理员凭据。"""
    admin_user = settings.FIRST_SUPERUSER or ""
    admin_pass = settings.FIRST_SUPERUSER_PASSWORD or ""
    return hmac.compare_digest(username, admin_user) and hmac.compare_digest(password, admin_pass)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_optional),
) -> dict[str, Any]:
    """兼容旧 API：返回 dict 用户对象。

    新代码请用 app.auth.instance.current_active_user（返回 ORM User）。
    """
    from app.database import get_db

    token: str | None = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("__Host-token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role", "user")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的令牌")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效的令牌") from None

    if user_id == 0 and role == "admin":
        return {
            "id": 0,
            "username": payload.get("username", "admin"),
            "role": "admin",
            "email": "",
            "created_at": "",
        }

    db = get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        user = User(**row)
        return {
            "id": user.id if user.id is not None else 0,
            "username": user.username,
            "role": user.role,
            "created_at": user.created_at or "",
            "email": user.email,
            "is_active": user.is_active,
        }
    finally:
        db.close()


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """兼容旧 API：要求管理员。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user