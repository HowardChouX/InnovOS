"""UserManager 测试。"""
import asyncio

import pytest
from fastapi_users.exceptions import InvalidPasswordException
from unittest.mock import MagicMock

from app.auth.users import UserManager


def test_user_manager_has_secrets():
    """UserManager 必须配置 reset_password_token_secret 和 verification_token_secret。"""
    assert UserManager.reset_password_token_secret is not None
    assert UserManager.verification_token_secret is not None


def test_validate_password_too_short():
    """密码 < 8 位应抛出 InvalidPasswordException。"""
    mgr = UserManager(MagicMock())
    with pytest.raises(InvalidPasswordException) as exc_info:
        asyncio.run(mgr.validate_password("12345", None))
    assert exc_info.value.reason == "密码至少 8 位"


def test_validate_password_ok():
    """密码 >= 8 位通过。"""
    mgr = UserManager(MagicMock())
    asyncio.run(mgr.validate_password("test1234", None))  # 不抛异常即通过


def test_on_after_register_sends_sms(monkeypatch):
    from app.auth.users import UserManager
    from app.services.sms_client import SmsClient

    sent: list[tuple[str, str]] = []

    class _FakeSms:
        async def send_code(self, phone, template_code):
            sent.append((phone, template_code))

    monkeypatch.setattr(SmsClient, "send_code", _FakeSms.send_code)
    um = UserManager.__new__(UserManager)
    # User 占位
    class _U:
        id = 1
        email = "a@b.com"
        phone = "13800000000"
    import asyncio
    asyncio.run(um.on_after_register(_U(), None))
    assert len(sent) == 1
    assert sent[0][0] == "13800000000"