"""InnovOSJWTStrategy 测试 - token_version 撤销机制。"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.auth.strategy import InnovOSJWTStrategy
from app.core.config import settings


def test_write_token_includes_token_version():
    """write_token 应在 payload 中注入 token_version。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    user = MagicMock()
    user.id = 42
    user.token_version = 3

    token = asyncio.run(strategy.write_token(user))
    assert isinstance(token, str)

    from fastapi_users.jwt import decode_jwt
    data = decode_jwt(
        token, settings.SECRET_KEY,
        ["fastapi-users:auth"], algorithms=["HS256"],
    )
    assert data["sub"] == "42"
    assert data["token_version"] == 3


def test_read_token_rejects_revoked():
    """token_version 不匹配时应返回 None（已撤销）。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    user = MagicMock()
    user.id = 42
    user.token_version = 1
    token = asyncio.run(strategy.write_token(user))

    # 模拟用户 token_version 已升级到 2（被撤销）
    user.token_version = 2
    user_manager = MagicMock()
    user_manager.parse_id = lambda x: int(x)
    user_manager.get = AsyncMock(return_value=user)

    result = asyncio.run(strategy.read_token(token, user_manager))
    assert result is None


def test_read_token_valid():
    """token_version 匹配时返回 user。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    user = MagicMock()
    user.id = 42
    user.token_version = 1
    token = asyncio.run(strategy.write_token(user))

    user_manager = MagicMock()
    user_manager.parse_id = lambda x: int(x)
    user_manager.get = AsyncMock(return_value=user)

    result = asyncio.run(strategy.read_token(token, user_manager))
    assert result is user