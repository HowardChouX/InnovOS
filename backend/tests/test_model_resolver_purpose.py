"""
TDD 测试: ModelResolver.purpose 解析

覆盖:
1. purpose=chat → chat_model
2. purpose=evaluation → chat_model
3. purpose=conversion → chat_model
4. purpose=extract → extract_model
5. purpose=embedding → embedding_model
6. purpose=rerank → rerank_model
7. 未知 purpose → ValueError
8. chat_model 未配置 → None
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _patch_db_with_settings(monkeypatch, settings: dict):
    """mock app.database.get_db 让 ModelResolver.get_assigned_settings 返 settings。"""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    # 模拟 fetchall 返回 [(key, value), ...]
    rows = [(k, v) for k, v in settings.items()]
    mock_cursor.fetchall.return_value = rows
    mock_db.execute.return_value = mock_cursor
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)


class TestPurposeToSettingKey:
    @pytest.mark.parametrize(
        "purpose,expected_key",
        [
            ("chat", "chat_model"),
            ("evaluation", "chat_model"),
            ("conversion", "chat_model"),
            ("extract", "extract_model"),
            ("embedding", "embedding_model"),
            ("rerank", "rerank_model"),
            ("ocr", "ocr_model"),
        ],
    )
    def test_known_purposes_map_correctly(
        self, monkeypatch, purpose, expected_key
    ):
        _patch_db_with_settings(
            monkeypatch,
            {
                "chat_model": "openai:gpt-4",
                "extract_model": "openai:gpt-4",
                "embedding_model": "openai:emb-1",
                "rerank_model": "openai:rerank-1",
                "ocr_model": "openai:ocr-1",
            },
        )
        from app.algorithm.model_resolver import ModelResolver

        key = ModelResolver.purpose_to_setting_key(purpose)
        assert key == expected_key

    def test_unknown_purpose_raises(self):
        from app.algorithm.model_resolver import ModelResolver

        with pytest.raises(ValueError, match="unknown|invalid"):
            ModelResolver.purpose_to_setting_key("nonsense")


class TestResolveByPurpose:
    def test_resolve_chat_returns_resolved_model(self, monkeypatch):
        _patch_db_with_settings(
            monkeypatch,
            {
                "chat_model": "openai:gpt-4",
                "extract_model": "",
                "embedding_model": "",
                "rerank_model": "",
                "ocr_model": "",
            },
        )
        # mock _get_provider_api_key 返 dummy key
        monkeypatch.setattr(
            "app.algorithm.model_service._get_provider_api_key",
            lambda pid: "fake-key" if pid else None,
        )
        # mock model_providers SELECT 返 host
        mock_db = monkeypatch.setattr  # 上面已 mock 过了;再 mock 第二次查询
        # 因为 model_resolver 调两次 get_db(),我们需要让两次都返相同 mock
        # 直接构造带 host 的 cursor
        from app.algorithm.model_resolver import ModelResolver

        # 重设 mock:让第二次 SELECT 返 host
        # 简单做法:让 mock_db.execute 根据 SQL 返回不同 cursor
        # 上面 _patch_db_with_settings 已设过 — 重新覆盖
        from app.database import get_db as real_get_db

        cursor_calls = {"count": 0}

        def get_db_factory():
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            cursor_calls["count"] += 1
            if cursor_calls["count"] == 1:
                # 第一次:system_settings SELECT
                mock_cursor.fetchall.return_value = [
                    {"key": "chat_model", "value": "openai:gpt-4"}
                ]
            else:
                # 第二次:model_providers SELECT
                mock_cursor.fetchone.return_value = {"api_host": "https://api.openai.com/v1"}
            mock_db.execute.return_value = mock_cursor
            return mock_db

        monkeypatch.setattr("app.database.get_db", get_db_factory)

        result = ModelResolver.resolve_for_purpose("chat")
        assert result is not None
        assert result.provider_id == "openai"
        assert result.model_id == "gpt-4"
        assert result.api_host == "https://api.openai.com/v1"

    def test_resolve_returns_none_when_chat_model_not_configured(self, monkeypatch):
        # 全部 setting 为空
        from app.algorithm.model_resolver import ModelResolver

        def get_db_factory():
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_db.execute.return_value = mock_cursor
            return mock_db

        monkeypatch.setattr("app.database.get_db", get_db_factory)

        result = ModelResolver.resolve_for_purpose("chat")
        assert result is None