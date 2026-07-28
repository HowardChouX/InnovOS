"""认证异常处理测试。"""
import asyncio
from unittest.mock import MagicMock

from fastapi_users import exceptions as fu_exceptions

from app.auth.exceptions import fastapi_users_exception_handler


def test_user_already_exists_returns_400():
    exc = fu_exceptions.UserAlreadyExists()
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 400
    assert "该邮箱已注册" in response.body.decode("utf-8")


def test_user_not_exists_returns_404():
    exc = fu_exceptions.UserNotExists()
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 404


def test_invalid_password_uses_reason():
    exc = fu_exceptions.InvalidPasswordException(reason="密码至少 8 位")
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 400
    assert "密码至少 8 位" in response.body.decode("utf-8")