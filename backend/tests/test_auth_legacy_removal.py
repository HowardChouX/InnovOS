"""update_user 直接设置 is_superuser（role 字段已移除）。

验证 update_user 修改 is_superuser 的行为：
  - is_superuser=True  ⇒ 提升为管理员
  - is_superuser=False ⇒ 降为普通用户
  - 未传 is_superuser  ⇒ 保持不变

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
        is_verified=True, username="admin", token_version=0,
    )


class TestUpdateUserSuperuser:
    """update_user 直接设置 is_superuser。"""

    def test_sets_is_superuser_true(self, mock_db, orm_admin):
        from app.api.admin.users import UpdateUserInput, update_user

        mock_db.add_row(
            "users",
            username="alice",
            email="alice@x.com",
            hashed_password="hashed",
            is_active=1,
            is_superuser=False,
        )

        with patch("app.database.get_db", return_value=mock_db):
            result = update_user(
                user_id=1, body=UpdateUserInput(is_superuser=True), _admin=orm_admin
            )

        assert result["code"] == 200
        row = mock_db._table("users")[1]
        assert row["is_superuser"] is True, "is_superuser=True 必须生效"

    def test_sets_is_superuser_false(self, mock_db, orm_admin):
        from app.api.admin.users import UpdateUserInput, update_user

        mock_db.add_row(
            "users",
            username="bob",
            email="bob@x.com",
            hashed_password="hashed",
            is_active=1,
            is_superuser=True,
        )

        with patch("app.database.get_db", return_value=mock_db):
            result = update_user(
                user_id=1, body=UpdateUserInput(is_superuser=False), _admin=orm_admin
            )

        assert result["code"] == 200
        row = mock_db._table("users")[1]
        assert row["is_superuser"] is False, "is_superuser=False 必须生效"

    def test_no_superuser_field_leaves_it_unchanged(self, mock_db, orm_admin):
        """body 不含 is_superuser 时（仅改 is_active），is_superuser 必须保持不变。"""
        from app.api.admin.users import UpdateUserInput, update_user

        mock_db.add_row(
            "users",
            username="carol",
            email="carol@x.com",
            hashed_password="hashed",
            is_active=1,
            is_superuser=True,
        )

        with patch("app.database.get_db", return_value=mock_db):
            result = update_user(
                user_id=1, body=UpdateUserInput(is_active=False), _admin=orm_admin
            )

        assert result["code"] == 200
        row = mock_db._table("users")[1]
        assert row["is_superuser"] is True, "未传 is_superuser 时不应被改动"
