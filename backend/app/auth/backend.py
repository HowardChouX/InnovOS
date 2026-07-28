"""认证后端 - CookieTransport + InnovOSJWTStrategy。"""
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
)

from app.auth.strategy import InnovOSJWTStrategy
from app.core.config import settings

# Cookie 为主通道，保持 __Host-token 名称（前端零改动）
# __Host- 前缀要求: Secure=True, Path=/, 无 Domain
cookie_transport = CookieTransport(
    cookie_name="__Host-token",
    cookie_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> InnovOSJWTStrategy:
    return InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)