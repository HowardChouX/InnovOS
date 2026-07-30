"""旧认证实现的兼容垫片。

仅供过渡期使用，新代码请用 app.auth.instance 的 current_active_user/current_superuser。

重要：登录已迁移到 FastAPI Users（app.auth.strategy.InnovOSJWTStrategy 签发 token，
payload 形如 {sub, aud, token_version}）。本垫片仍需解码这些新 token 供 25+ 旧路由使用，
因此解码时必须传入与签发端一致的 audience，并从 sub/user_id 两种 claim 中取用户 ID。
"""
import hmac
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
        # 必须传 audience：新 token 含 aud 声明，不校验会抛 InvalidAudienceError；
        # 同时强制校验可拒绝 reset/verify token（同 SECRET_KEY 但 audience 不同），
        # 防止重置密码链接的 token 被拿来冒充用户访问业务接口。
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], audience=TOKEN_AUDIENCE
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效的令牌") from None

    # 新 token 的用户 ID 在 sub（字符串）；解析为 int。
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
        # 直接从 row 读取（DB 列为 hashed_password，旧 Pydantic User 模型已不适用）
        created_at = row.get("created_at")
        return {
            "id": row["id"] if row.get("id") is not None else 0,
            "username": row.get("username") or "",
            "role": row.get("role") or "user",
            "created_at": str(created_at) if created_at else "",
            "email": row.get("email") or "",
            "is_active": row.get("is_active", 1),
        }
    finally:
        db.close()


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """兼容旧 API：要求管理员。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
