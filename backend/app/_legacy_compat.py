"""旧认证实现的兼容垫片。

仅供过渡期使用，新代码请用 app.auth.instance 的 current_active_user/current_superuser。

重要：登录已迁移到 FastAPI Users（app.auth.strategy.InnovOSJWTStrategy 签发 token，
payload 形如 {sub, aud, token_version}）。本垫片仍需解码这些新 token 供 25+ 旧路由使用，
因此解码时必须传入与签发端一致的 audience，并从 sub/user_id 两种 claim 中取用户 ID。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.strategy import TOKEN_AUDIENCE
from app.core.config import settings

ACCESS_TOKEN_EXPIRE_HOURS = 24

SECRET_KEY: str = settings.SECRET_KEY
ALGORITHM = "HS256"

_security_optional = HTTPBearer(auto_error=False)

# Cookie 名：生产 __Host-token，开发 token（HTTP 下 Secure cookie 无法发送）
_COOKIE_NAME = "__Host-token" if settings.ENVIRONMENT == "production" else "token"
_COOKIE_SECURE = settings.ENVIRONMENT == "production"


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
    """设置 token cookie（环境自适应 cookie 名）。"""
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )


def clear_token_cookie(response: Response) -> None:
    """清除 token cookie。"""
    response.set_cookie(
        key=_COOKIE_NAME, value="", httponly=True, secure=_COOKIE_SECURE,
        max_age=0, path="/",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_optional),
) -> dict[str, Any]:
    """返回 dict 用户对象。新代码请用 app.auth.instance.current_active_user。"""
    from app.database import get_db

    token: str | None = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get(_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], audience=TOKEN_AUDIENCE
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效的令牌") from None

    sub = payload.get("sub")
    user_id: int | None = None
    if sub is not None:
        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            user_id = None
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的令牌")

    db = get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        created_at = row.get("created_at")
        return {
            "id": row["id"] if row.get("id") is not None else 0,
            "username": row.get("username") or "",
            "is_superuser": bool(row.get("is_superuser", False)),
            "created_at": str(created_at) if created_at else "",
            "email": row.get("email") or "",
            "is_active": row.get("is_active", 1),
        }
    finally:
        db.close()


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """要求管理员。"""
    if not user.get("is_superuser"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
