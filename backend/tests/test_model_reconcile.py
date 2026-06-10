"""测试模型同步管线 — reconcile (diff + apply)"""
import json
import pytest
from unittest.mock import MagicMock


def make_row(provider_id="silicon", models=None):
    """创建模拟数据库行。"""
    return {
        "id": 1,
        "provider_id": provider_id,
        "name": "SiliconFlow",
        "protocol": "openai",
        "api_host": "https://api.siliconflow.cn",
        "api_key_encrypted": "enc_key",
        "api_model": "",
        "models": json.dumps(models or []),
        "is_enabled": 1,
        "priority": 1,
        "max_rpm": 60,
        "current_rpm": 0,
        "request_count": 0,
        "last_used_at": None,
        "created_at": "2025-01-01 00:00:00",
    }


def _mock_db(monkeypatch, row):
    """Setup mock DB returning given row, also patch model_service's local get_db reference."""
    mock_conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    mock_conn.execute.return_value = cursor
    monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
    monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: mock_conn)
    return mock_conn


class TestReconcileModels:
    """reconcile_models() — diff 计算"""

    def test_added_models(self, monkeypatch):
        """API 发现新模型应出现在 added 列表"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, make_row(provider_id="test", models=[
            {"id": "old-model", "capabilities": ["chat"]},
        ]))

        detected = [
            {"id": "old-model", "capabilities": ["chat"]},
            {"id": "new-model", "capabilities": ["embedding"]},
        ]
        result = model_service.reconcile_models("test", detected)
        assert result is not None
        added_ids = [m["id"] for m in result["added"]]
        assert "new-model" in added_ids
        assert result["removed"] == []
        assert result["unchanged"] == [{"id": "old-model"}]

    def test_removed_models(self, monkeypatch):
        """API 不再提供的模型应出现在 removed 列表"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, make_row(provider_id="test", models=[
            {"id": "gone-model", "capabilities": ["chat"]},
            {"id": "kept-model", "capabilities": ["chat"]},
        ]))

        detected = [
            {"id": "kept-model", "capabilities": ["chat"]},
        ]
        result = model_service.reconcile_models("test", detected)
        assert result is not None
        assert result["removed"] == [{"id": "gone-model"}]
        assert result["added"] == []
        assert result["unchanged"] == [{"id": "kept-model"}]

    def test_both_added_and_removed(self, monkeypatch):
        """同时有新增和移除的模型"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, make_row(provider_id="test", models=[
            {"id": "model-a", "capabilities": ["chat"]},
            {"id": "model-b", "capabilities": ["chat"]},
        ]))

        detected = [
            {"id": "model-b", "capabilities": ["chat"]},
            {"id": "model-c", "capabilities": ["embedding"]},
        ]
        result = model_service.reconcile_models("test", detected)
        assert result is not None
        assert result["removed"] == [{"id": "model-a"}]
        assert result["unchanged"] == [{"id": "model-b"}]
        added_ids = [m["id"] for m in result["added"]]
        assert "model-c" in added_ids

    def test_no_changes(self, monkeypatch):
        """无变化时应返回空 diff"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, make_row(provider_id="test", models=[
            {"id": "model-a", "capabilities": ["chat"]},
        ]))

        detected = [
            {"id": "model-a", "capabilities": ["chat"]},
        ]
        result = model_service.reconcile_models("test", detected)
        assert result is not None
        assert result["added"] == []
        assert result["removed"] == []
        assert result["unchanged"] == [{"id": "model-a"}]

    def test_provider_not_found(self, monkeypatch):
        """不存在的 provider 应返回 None"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, None)  # fetchone returns None

        result = model_service.reconcile_models("nonexistent", [])
        assert result is None

    def test_stored_models_use_string_format(self, monkeypatch):
        """兼容旧格式：stored models 是纯字符串列表"""
        from app.algorithm.model_service import model_service

        _mock_db(monkeypatch, make_row(provider_id="test", models=[
            "old-string-model",
        ]))

        detected = [
            {"id": "old-string-model", "capabilities": ["chat"]},
            {"id": "new-model", "capabilities": ["chat"]},
        ]
        result = model_service.reconcile_models("test", detected)
        assert result is not None
        assert result["unchanged"] == [{"id": "old-string-model"}]
        assert len(result["added"]) > 0


class TestReconcileApply:
    """reconcile_apply() — 应用 diff"""

    def _mock_db_for_apply(self, monkeypatch, row):
        """reconcile_apply does 2 SELECTs (before + after update)."""
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [row, row]
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: mock_conn)
        return mock_conn

    def test_add_models(self, monkeypatch):
        """添加模型到存储列表"""
        from app.algorithm.model_service import model_service

        row = make_row(provider_id="test", models=[
            {"id": "existing", "capabilities": ["chat"]},
        ])
        self._mock_db_for_apply(monkeypatch, row)

        result = model_service.reconcile_apply("test", to_add=["new-model"], to_remove=[])
        assert result is not None

    def test_remove_models(self, monkeypatch):
        """从存储列表删除模型"""
        from app.algorithm.model_service import model_service

        row = make_row(provider_id="test", models=[
            {"id": "keep", "capabilities": ["chat"]},
            {"id": "remove", "capabilities": ["chat"]},
        ])
        self._mock_db_for_apply(monkeypatch, row)

        result = model_service.reconcile_apply("test", to_add=[], to_remove=["remove"])
        assert result is not None

    def test_provider_not_found(self, monkeypatch):
        """不存在的 provider 应返回 None"""
        from app.algorithm.model_service import model_service

        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.algorithm.model_service.get_db", lambda: mock_conn)

        result = model_service.reconcile_apply("nonexistent", [], [])
        assert result is None

    def test_add_duplicate_is_idempotent(self, monkeypatch):
        """添加已存在的模型不应产生重复"""
        from app.algorithm.model_service import model_service

        row = make_row(provider_id="test", models=[
            {"id": "model-a", "capabilities": ["chat"]},
        ])
        self._mock_db_for_apply(monkeypatch, row)

        result = model_service.reconcile_apply("test", to_add=["model-a"], to_remove=[])
        assert result is not None

    def test_remove_non_existent_is_idempotent(self, monkeypatch):
        """删除不存在的模型不应报错"""
        from app.algorithm.model_service import model_service

        row = make_row(provider_id="test", models=[
            {"id": "model-a", "capabilities": ["chat"]},
        ])
        self._mock_db_for_apply(monkeypatch, row)

        result = model_service.reconcile_apply("test", to_add=[], to_remove=["nonexistent"])
        assert result is not None
