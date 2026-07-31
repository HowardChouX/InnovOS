"""认证后端 - CookieTransport + InnovOSJWTStrategy。"""
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
)

from app.auth.strategy import TOKEN_AUDIENCE, InnovOSJWTStrategy
from app.core.config import settings

# Cookie 为主通道。
# 生产环境使用 __Host-token（要求 Secure=True, Path=/, 无 Domain）
# 开发环境使用 token（HTTP localhost 下 Secure cookie 不会发送，需降级）
if settings.ENVIRONMENT == "production":
    _cookie_name = "__Host-token"
    _cookie_secure = True
else:
    _cookie_name = "token"
    _cookie_secure = False

cookie_transport = CookieTransport(
    cookie_name=_cookie_name,
    cookie_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    cookie_secure=_cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> InnovOSJWTStrategy:
    return InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        token_audience=TOKEN_AUDIENCE,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
