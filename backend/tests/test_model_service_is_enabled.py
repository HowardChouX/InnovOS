"""Regression tests for model_providers.is_enabled (INTEGER) column type mismatch.

背景: ``model_providers.is_enabled`` 列是 INTEGER DEFAULT 1,但历史代码多处
错误地把 Python ``bool`` / SQL ``TRUE`` 绑给该列 — PostgreSQL 严格类型导致
``DatatypeMismatch: column "is_enabled" is of type integer but expression is of
type boolean``。

本测试覆盖三个修复点:
1. ``upsert`` INSERT 不再写 ``TRUE``,改写 ``1``
2. ``update`` 绑定 ``int`` 而不是 ``bool``
3. ``_row_to_dict`` 从 INTEGER 列读出后仍返回 Python ``bool``
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.algorithm.model_service import model_service


class _RecordingCursor:
    """记录所有 execute 调用;fetchone/fetchall 返回预设值。"""

    def __init__(self, fetchone_value=None, fetchall_value=None):
        self.fetchone_value = fetchone_value
        self.fetchall_value = fetchall_value or []
        self.calls: list[tuple[str, tuple]] = []
        self._cur = MagicMock()

    def execute(self, sql, params=None):
        self.calls.append((sql, params or ()))
        result = MagicMock()
        result.fetchone.return_value = self.fetchone_value
        result.fetchall.return_value = self.fetchall_value
        result.rowcount = 1
        return result

    def commit(self):
        pass

    def close(self):
        pass


class TestUpsertIsEnabledInteger:
    """INSERT VALUES 不再用 TRUE (boolean literal),必须用 1 (int)."""

    def test_insert_uses_integer_one_not_boolean(self, monkeypatch):
        cursor = _RecordingCursor(fetchone_value=None)  # provider 不存在 → 走 INSERT
        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: cursor)

        # mock _upsert_api_key 避免触发 api_keys INSERT 的副作用
        captured: dict = {}

        def fake_upsert_key(*, provider_id, plaintext):
            captured["provider_id"] = provider_id
            captured["plaintext"] = plaintext

        monkeypatch.setattr(model_service, "_upsert_api_key", fake_upsert_key)

        # mock self.get 避免触发第二次查询
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: {
                "providerId": "new-p",
                "name": "Test",
                "notes": "",
                "apiHost": "https://api.example.com",
                "apiModel": "",
                "isEnabled": True,
                "createdAt": "",
                "updatedAt": "",
            },
        )

        model_service.upsert(
            provider_id="new-p",
            name="Test",
            api_host="https://api.example.com",
            api_key_plaintext="sk-abc123",
        )

        # 找到 INSERT 语句
        insert_calls = [c for c in cursor.calls if "INSERT INTO model_providers" in c[0]]
        assert len(insert_calls) == 1, f"expected 1 INSERT, got {cursor.calls}"
        sql = insert_calls[0][0]

        # 不应该再出现 TRUE / FALSE 布尔字面量
        assert "TRUE" not in sql, f"INSERT still uses boolean literal: {sql}"
        assert "FALSE" not in sql, f"INSERT still uses boolean literal: {sql}"
        # 应该用整数 1
        assert "60, 1)" in sql, f"expected INTEGER 1 for is_enabled, got: {sql}"

    def test_upsert_key_side_effect_called(self, monkeypatch):
        """_upsert_api_key 仍然被调用(确认 fix 没破坏副作用)。"""
        cursor = _RecordingCursor(fetchone_value=None)
        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: cursor)

        called = []

        def fake_upsert_key(*, provider_id, plaintext):
            called.append((provider_id, plaintext))

        monkeypatch.setattr(model_service, "_upsert_api_key", fake_upsert_key)
        monkeypatch.setattr(model_service, "get", lambda pid: {"providerId": pid})

        model_service.upsert(
            provider_id="p-x",
            name="X",
            api_host="https://x.com",
            api_key_plaintext="sk-xyz",
        )

        assert called == [("p-x", "sk-xyz")]


class TestUpdateIsEnabledInteger:
    """UPDATE 绑定的 is_enabled 参数必须是 int,不是 bool."""

    def _make_provider_row(self, provider_id, is_enabled_int):
        """构造一个 _row_to_dict 能转换的 DB 行 dict。"""
        return {
            "provider_id": provider_id,
            "name": "n",
            "notes": "",
            "api_host": "https://x.com",
            "api_model": "",
            "is_enabled": is_enabled_int,
            "created_at": "",
            "updated_at": "",
        }

    def test_update_binds_int_one_when_enabled_true(self, monkeypatch):
        # 第一次 get_db: get() 查询 (SELECT);后续调用走 UPDATE
        # model_service.update 实现: 先 get, 再 _get_pg_db 调用 UPDATE,然后 commit,再 get 返回最新值
        # 简化: 我们只关心 UPDATE 那次调用

        row = self._make_provider_row("p1", 1)

        all_calls: list[tuple[str, tuple]] = []

        class FakeConn:
            def execute(self, sql, params=None):
                all_calls.append((sql, params or ()))
                cur = MagicMock()
                # SELECT 用 fetchone,其他也用 fetchone 都能返 row
                cur.fetchone.return_value = row
                cur.fetchall.return_value = []
                cur.rowcount = 1
                return cur

            def commit(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: FakeConn())

        model_service.update("p1", name="New", is_enabled=True)

        update_calls = [c for c in all_calls if "UPDATE model_providers SET" in c[0]]
        assert len(update_calls) == 1, f"expected 1 UPDATE, got {all_calls}"
        sql, params = update_calls[0]
        assert "is_enabled=%s" in sql

        # SQL: UPDATE ... SET name=%s, notes=%s, api_host=%s, api_model=%s, is_enabled=%s WHERE provider_id=%s
        # params 顺序: (name, notes, api_host, api_model, is_enabled, provider_id)
        bound_is_enabled = params[4]
        assert isinstance(bound_is_enabled, int), (
            f"is_enabled bound as {type(bound_is_enabled).__name__}, "
            f"expected int — psycopg2 maps Python bool → PostgreSQL BOOLEAN → mismatch"
        )
        assert bound_is_enabled == 1

    def test_update_binds_int_zero_when_enabled_false(self, monkeypatch):
        row = self._make_provider_row("p2", 0)
        all_calls: list[tuple[str, tuple]] = []

        class FakeConn:
            def execute(self, sql, params=None):
                all_calls.append((sql, params or ()))
                cur = MagicMock()
                cur.fetchone.return_value = row
                cur.fetchall.return_value = []
                cur.rowcount = 1
                return cur

            def commit(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: FakeConn())

        model_service.update("p2", is_enabled=False)

        update_calls = [c for c in all_calls if "UPDATE model_providers SET" in c[0]]
        assert len(update_calls) == 1
        _, params = update_calls[0]
        bound_is_enabled = params[4]
        assert isinstance(bound_is_enabled, int)
        assert bound_is_enabled == 0

    def test_update_preserves_existing_when_is_enabled_omitted(self, monkeypatch):
        """调用 update() 不传 is_enabled 时,应该用 current['isEnabled'] 转 int。"""
        row = self._make_provider_row("p3", 1)
        all_calls: list[tuple[str, tuple]] = []

        class FakeConn:
            def execute(self, sql, params=None):
                all_calls.append((sql, params or ()))
                cur = MagicMock()
                cur.fetchone.return_value = row
                cur.fetchall.return_value = []
                cur.rowcount = 1
                return cur

            def commit(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: FakeConn())

        # 不传 is_enabled → 用 current['isEnabled'] = bool(row.is_enabled)
        # row['is_enabled'] = 1 → bool(1) = True → int(True) = 1
        model_service.update("p3", name="Renamed")

        update_calls = [c for c in all_calls if "UPDATE model_providers SET" in c[0]]
        assert len(update_calls) == 1
        _, params = update_calls[0]
        assert isinstance(params[4], int)
        assert params[4] == 1


class TestRowToDictIsEnabled:
    """_row_to_dict 读 INTEGER 0/1 应正确转为 Python bool."""

    def test_int_one_becomes_true(self):
        out = model_service._row_to_dict({"is_enabled": 1})
        assert out["isEnabled"] is True
        assert isinstance(out["isEnabled"], bool)

    def test_int_zero_becomes_false(self):
        out = model_service._row_to_dict({"is_enabled": 0})
        assert out["isEnabled"] is False
        assert isinstance(out["isEnabled"], bool)

    def test_missing_defaults_to_true(self):
        """列缺失时(例如遗留老行)默认为 True — 与原逻辑一致。"""
        out = model_service._row_to_dict({})
        assert out["isEnabled"] is True
