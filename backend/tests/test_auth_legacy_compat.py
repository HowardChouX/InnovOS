"""回归测试：新签发端（InnovOSJWTStrategy）↔ 旧解码端（_legacy_compat）互操作。

背景：登录迁移到 FastAPI Users 后，token 由 InnovOSJWTStrategy 签发
（payload 形如 {sub, aud=["fastapi-users:auth"], token_version}），
但 25+ 业务路由仍经 app._legacy_compat.get_current_user 解码。
此前旧解码端未传 audience、只读 user_id claim、且用已失效的 Pydantic User 模型，
导致新 token 一律解码失败 → 登录后所有业务接口 401。本测试锁死该互操作契约。
"""
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.auth.strategy import TOKEN_AUDIENCE, InnovOSJWTStrategy
from app.core.config import settings


def _issue_token(user_id: int, token_version: int = 0) -> str:
    """用真实的登录签发策略生成 token（与生产路径一致）。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY, lifetime_seconds=3600
    )
    user = MagicMock()
    user.id = user_id
    user.token_version = token_version
    import asyncio

    return asyncio.run(strategy.write_token(user))


def _request_with_cookie(token: str):
    """构造仅含 cookies 的最小 Request 替身。"""
    req = MagicMock()
    req.cookies = {"__Host-token": token}
    return req


class TestLegacyCompatDecodesNewToken:
    def test_decodes_fastapi_users_token(self):
        """新策略签发的 token 必须能被旧垫片解码出正确的用户。"""
        from app._legacy_compat import get_current_user

        token = _issue_token(user_id=7)
        row = {
            "id": 7,
            "username": "alice",
            "email": "alice@example.com",
            "role": "user",
            "is_active": 1,
            "created_at": "2026-01-01 00:00:00",
            "hashed_password": "x",  # 新列名，旧 Pydantic 模型无此字段
        }
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = row

        with patch("app.database.get_db", return_value=db):
            user = get_current_user(_request_with_cookie(token), credentials=None)

        assert user["id"] == 7
        assert user["username"] == "alice"
        assert user["email"] == "alice@example.com"
        assert user["role"] == "user"

    def test_rejects_reset_password_token(self):
        """同 SECRET_KEY 的 reset token（不同 audience）不得被当作登录 token。

        这是安全边界：若解码端不校验 audience，重置密码链接里的 token
        （payload 也含 sub=用户 id）就能越权访问所有业务接口。
        """
        from app._legacy_compat import get_current_user

        reset_token = jwt.encode(
            {"sub": "7", "aud": ["fastapi-users:reset"], "exp": 9999999999},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        with patch("app.database.get_db") as mock_get_db:
            with pytest.raises(HTTPException) as exc:
                get_current_user(_request_with_cookie(reset_token), credentials=None)
        assert exc.value.status_code == 401
        mock_get_db.assert_not_called()  # 解码即失败，不应触达 DB

    def test_missing_token_is_401(self):
        from app._legacy_compat import get_current_user

        req = MagicMock()
        req.cookies = {}
        with pytest.raises(HTTPException) as exc:
            get_current_user(req, credentials=None)
        assert exc.value.status_code == 401


def test_token_audience_is_single_source():
    """签发端与解码端必须引用同一 audience 常量，防止两处硬编码漂移。"""
    import app._legacy_compat as compat

    assert compat.TOKEN_AUDIENCE == TOKEN_AUDIENCE == ["fastapi-users:auth"]
