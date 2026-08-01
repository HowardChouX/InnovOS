"""Tests for admin users delete — foreign key dependency handling.

直接调用 endpoint 函数,避免 TestClient 触发 app.main 启动事件
(沙箱无 PostgreSQL/Redis 时 startup 会卡住)。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _FakeCursor:
    """按 SQL 关键字分发返回值的最小 mock。"""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params=None):
        self.calls.append((sql, params or ()))
        cur = MagicMock()
        sql_l = sql.strip().lower()
        # SELECT COUNT(*) FROM <table> WHERE user_id=?
        if sql_l.startswith("select count"):
            cur.fetchone.return_value = {"n": self._count_for(sql_l)}
            return cur
        # SELECT id [FROM users WHERE id=... target existence check]
        # 复用同一个分支:总是返回存在,避免邮件/ID 字段缺失导致 KeyError
        if sql_l.startswith("select id"):
            cur.fetchone.return_value = {"id": 7, "email": "admin@innovos.com"}
            return cur
        # DELETE
        if sql_l.startswith("delete"):
            cur.rowcount = 1
            return cur
        # UPDATE
        if sql_l.startswith("update"):
            cur.rowcount = 5
            return cur
        cur.fetchone.return_value = None
        return cur

    @staticmethod
    def _count_for(sql_l: str) -> int:
        # 简易:从表名提取计数;测试用 fixture 覆盖
        if "tasks" in sql_l:
            return 12
        if "solutions" in sql_l:
            return 4
        return 0

    def commit(self):
        pass

    def close(self):
        pass


def _mock_db(monkeypatch, fake_cursor: _FakeCursor | None = None):
    fc = fake_cursor or _FakeCursor()
    # users.py 在函数体内 import get_db,需 patch 源模块 app.database.get_db
    monkeypatch.setattr("app.database.get_db", lambda: fc)
    return fc


def _bypass_auth(monkeypatch, admin_id: int = 99):
    """所有 admin 路由都要求 SuperUserDep,跳过鉴权。"""
    monkeypatch.setattr(
        "app.api.admin.users.SuperUserDep",
        lambda: MagicMock(id=admin_id, is_superuser=True),
    )


def _call_delete(monkeypatch, user_id: int, *, admin_id: int = 99, **query):
    """直接调用 endpoint 函数,绕开 FastAPI 依赖注入与 startup 钩子。

    调用前请先用 _mock_db() 或直接 monkeypatch.setattr("app.database.get_db", ...)
    完成 DB 注入,本函数不会再次 patch(避免覆盖测试用例自定义的 cursor)。
    """
    from app.api.admin import users as users_module
    admin_mock = MagicMock(id=admin_id, is_superuser=True)
    return users_module.delete_user(
        user_id=user_id,
        _admin=admin_mock,
        **query,
    )


class _FakeResponse:
    """模拟 FastAPI HTTPException 让 endpoint 函数能 raise 我们的捕获。"""

    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail


class TestDeleteUserDependencyDetection:
    def test_user_with_tasks_returns_409_with_dependency_list(self, monkeypatch):
        _bypass_auth(monkeypatch)
        _mock_db(monkeypatch)  # 默认 _FakeCursor: tasks=12, solutions=4
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _call_delete(monkeypatch, 7)
        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert "关联数据" in detail["message"]
        tables = {d["table"] for d in detail["dependencies"]}
        assert "tasks" in tables
        assert any("reassign_to" in s for s in detail["suggestions"])
        assert any("force=true" in s for s in detail["suggestions"])

    def test_user_with_no_dependencies_can_be_deleted(self, monkeypatch):
        _bypass_auth(monkeypatch)

        # 独立 cursor — 所有 COUNT 返回 {"n": 0},SELECT id/email 返回用户存在
        class ZeroCursor:
            def __init__(self):
                self.calls = []
            def execute(self, sql, params=None):
                self.calls.append((sql, params or ()))
                cur = MagicMock()
                sql_l = sql.strip().lower()
                if sql_l.startswith("select count"):
                    cur.fetchone.return_value = {"n": 0}
                elif sql_l.startswith("select id"):
                    cur.fetchone.return_value = {"id": 8, "email": "u@example.com"}
                cur.rowcount = 1
                return cur
            def commit(self): pass
            def close(self): pass

        monkeypatch.setattr("app.database.get_db", lambda: ZeroCursor())
        result = _call_delete(monkeypatch, 8)
        assert result["message"] == "已删除"
        assert result["user_id"] == 8


class TestDeleteUserReassign:
    def test_reassign_to_migrates_dependencies_then_deletes(self, monkeypatch):
        _bypass_auth(monkeypatch)
        fc = _mock_db(monkeypatch)
        # 但 reassign_to 路径会先调用 SELECT 来检查目标用户存在,需要兼容
        result = _call_delete(monkeypatch, 7, reassign_to=3)
        assert result["reassigned_to"] == 3
        assert result["forced"] is False

        update_calls = [c for c in fc.calls if c[0].strip().lower().startswith("update")]
        assert len(update_calls) >= 1, "reassign_to 应触发 UPDATE 迁移"
        delete_calls = [c for c in fc.calls if c[0].strip().lower().startswith("delete")]
        assert len(delete_calls) >= 1

    def test_reassign_to_self_returns_400(self, monkeypatch):
        _bypass_auth(monkeypatch)
        _mock_db(monkeypatch)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _call_delete(monkeypatch, 7, reassign_to=7)
        assert exc_info.value.status_code == 400
        assert "不能等于" in exc_info.value.detail


class TestDeleteUserForce:
    def test_force_cascades_dependency_deletion(self, monkeypatch):
        _bypass_auth(monkeypatch)
        fc = _mock_db(monkeypatch)
        result = _call_delete(monkeypatch, 7, force=True)
        assert result["forced"] is True

        # 应有 DELETE FROM <table> WHERE user_id=? 调用
        delete_calls = [
            c for c in fc.calls
            if c[0].strip().lower().startswith("delete") and "user_id" in c[0].lower()
        ]
        assert len(delete_calls) >= 1

    def test_force_and_reassign_to_mutually_exclusive(self, monkeypatch):
        _bypass_auth(monkeypatch)
        _mock_db(monkeypatch)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _call_delete(monkeypatch, 7, force=True, reassign_to=3)
        assert exc_info.value.status_code == 400
        assert "互斥" in exc_info.value.detail


class TestDeleteUserSafety:
    def test_cannot_delete_root_admin(self, monkeypatch):
        _bypass_auth(monkeypatch)
        _mock_db(monkeypatch)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _call_delete(monkeypatch, 0)
        assert exc_info.value.status_code == 400
        assert "根管理员" in exc_info.value.detail

    def test_cannot_delete_self(self, monkeypatch):
        _bypass_auth(monkeypatch, admin_id=7)
        _mock_db(monkeypatch)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _call_delete(monkeypatch, 7, admin_id=7)  # 传 admin_id=7 触发 self-delete 检查
        assert exc_info.value.status_code == 400
        assert "不能删除自己" in exc_info.value.detail
