"""Task 1: role 变更必须同步 is_superuser。

验证 update_user 修改 role 时，is_superuser 随之联动：
  - role → "admin"  ⇒ is_superuser = True
  - role → "user"   ⇒ is_superuser = False

直接调用 update_user 函数（patch get_db 为 MockDB），真实执行被测代码路径。
注：TestClient 因 starlette 1.3.1 / httpx 版本不兼容在当前环境挂起，
故采用直接函数调用方式（仍走完整 update_user 逻辑）。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.test_api_admin import MockDB


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def orm_admin():
    from app.db.models import User as OrmUser

    return OrmUser(
        id=1, email="admin@example.com",
        hashed_password="!", is_active=True, is_superuser=True,
        is_verified=True, username="admin", role="admin", token_version=0,
    )


class TestUpdateUserSyncsSuperuser:
    """update_user 修改 role 时必须同步 is_superuser。"""

    def test_role_admin_sets_is_superuser_true(self, mock_db, orm_admin):
        from app.api.admin.users import UpdateUserInput, update_user

        mock_db.add_row(
            "users",
            username="alice",
            email="alice@x.com",
            hashed_password="hashed",
            role="user",
            is_active=1,
            is_superuser=False,
        )

        with patch("app.database.get_db", return_value=mock_db):
            result = update_user(
                user_id=1, body=UpdateUserInput(role="admin"), _admin=orm_admin
            )

        assert result["code"] == 200
        row = mock_db._table("users")[1]
        assert row["role"] == "admin"
        assert row["is_superuser"] is True, (
            "role 改为 admin 后 is_superuser 必须同步为 True"
        )

    def test_role_user_sets_is_superuser_false(self, mock_db, orm_admin):
        from app.api.admin.users import UpdateUserInput, update_user

        mock_db.add_row(
            "users",
            username="bob",
            email="bob@x.com",
            hashed_password="hashed",
            role="admin",
            is_active=1,
            is_superuser=True,
        )

        with patch("app.database.get_db", return_value=mock_db):
            result = update_user(
                user_id=1, body=UpdateUserInput(role="user"), _admin=orm_admin
            )

        assert result["code"] == 200
        row = mock_db._table("users")[1]
        assert row["role"] == "user"
        assert row["is_superuser"] is False, (
            "role 改为 user 后 is_superuser 必须同步为 False"
        )
