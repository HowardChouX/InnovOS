"""
测试 model_resolver.py — 模型配置解析服务

Mock 数据库和 model_service，测试 3-tier fallback、配置解析。
"""

import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# ModelResolver.get_assigned_settings
# ═══════════════════════════════════════════════════════════════════

class TestGetAssignedSettings:
    def test_returns_all_keys(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"key": "chat_model", "value": "silicon:deepseek-v3"},
            {"key": "embedding_model", "value": "silicon:bge-large-zh"},
        ]
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        settings = ModelResolver.get_assigned_settings()
        assert settings["chat_model"] == "silicon:deepseek-v3"
        assert settings["embedding_model"] == "silicon:bge-large-zh"
        assert settings["rerank_model"] is None
        assert settings["ocr_model"] is None
        assert settings["extract_model"] is None

    def test_empty_db_returns_defaults(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        settings = ModelResolver.get_assigned_settings()
        assert settings == {
            "chat_model": None, "embedding_model": None,
            "rerank_model": None, "ocr_model": None, "extract_model": None,
        }

    def test_db_closed_after_query(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        ModelResolver.get_assigned_settings()
        assert mock_conn.close.called

    def test_sql_query_correct(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        ModelResolver.get_assigned_settings()
        sql = mock_conn.execute.call_args[0][0]
        assert "chat_model" in sql
        assert "embedding_model" in sql
        assert "rerank_model" in sql


# ═══════════════════════════════════════════════════════════════════
# ModelResolver.parse_composite_id
# ═══════════════════════════════════════════════════════════════════

class TestParseCompositeId:
    def test_standard_format(self):
        from app.algorithm.model_resolver import ModelResolver
        provider, model = ModelResolver.parse_composite_id("silicon:deepseek-v3")
        assert provider == "silicon"
        assert model == "deepseek-v3"

    def test_multi_colon(self):
        from app.algorithm.model_resolver import ModelResolver
        provider, model = ModelResolver.parse_composite_id("openai:gpt-4:latest")
        assert provider == "openai"
        assert model == "gpt-4:latest"

    def test_no_provider(self):
        from app.algorithm.model_resolver import ModelResolver
        provider, model = ModelResolver.parse_composite_id("gpt-4")
        assert provider == ""
        assert model == "gpt-4"

    def test_empty_string(self):
        from app.algorithm.model_resolver import ModelResolver
        provider, model = ModelResolver.parse_composite_id("")
        assert provider == ""
        assert model == ""


# ═══════════════════════════════════════════════════════════════════
# ModelResolver.resolve
# ═══════════════════════════════════════════════════════════════════

class TestResolve:
    def test_resolve_success(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"api_host": "https://api.siliconflow.cn"}
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr(
            "app.algorithm.model_service._get_provider_api_key",
            lambda pid: "env_key_silicon",
        )

        config = ModelResolver.resolve("silicon:deepseek-v3")
        assert config is not None
        assert config.provider_id == "silicon"
        assert config.model_id == "deepseek-v3"
        assert config.api_key == "env_key_silicon"
        assert config.api_host == "https://api.siliconflow.cn"

    def test_resolve_invalid_format_returns_none(self):
        from app.algorithm.model_resolver import ModelResolver
        assert ModelResolver.resolve("") is None
        assert ModelResolver.resolve(":model") is None

    def test_resolve_no_api_key_returns_none(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            "app.algorithm.model_service._get_provider_api_key",
            lambda pid: None,
        )
        config = ModelResolver.resolve("silicon:deepseek-v3")
        assert config is None

    def test_resolve_provider_not_in_db_returns_none(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr(
            "app.algorithm.model_service._get_provider_api_key",
            lambda pid: "key",
        )
        config = ModelResolver.resolve("unknown:model")
        assert config is None

    def test_db_sql_uses_provider_id_and_is_enabled(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"api_host": "https://api.test.com"}
        mock_conn.execute.return_value = mock_cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr(
            "app.algorithm.model_service._get_provider_api_key",
            lambda pid: "key",
        )
        ModelResolver.resolve("test:model")
        sql = mock_conn.execute.call_args[0][0]
        params = mock_conn.execute.call_args[0][1]
        assert "provider_id" in sql
        assert "is_enabled" in sql
        assert params == ("test",)


# ═══════════════════════════════════════════════════════════════════
# ModelResolver.resolve_chat / resolve_embedding / resolve_rerank
# ═══════════════════════════════════════════════════════════════════

class TestResolveChat:
    def test_resolve_chat_success(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": "openai:gpt-4", "embedding_model": None,
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        monkeypatch.setattr(
            ModelResolver, "resolve",
            staticmethod(lambda composite: MagicMock(
                provider_id="openai", model_id="gpt-4", api_key="key", api_host="host",
            )),
        )

        config = ModelResolver.resolve_chat()
        assert config is not None
        assert config.provider_id == "openai"

    def test_resolve_chat_not_configured(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": None, "embedding_model": None,
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        config = ModelResolver.resolve_chat()
        assert config is None

    def test_resolve_chat_empty_string(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": "", "embedding_model": None,
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        config = ModelResolver.resolve_chat()
        assert config is None


class TestResolveEmbedding:
    def test_resolve_embedding_success(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": None, "embedding_model": "silicon:bge-large-zh",
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        monkeypatch.setattr(
            ModelResolver, "resolve",
            staticmethod(lambda composite: MagicMock(
                provider_id="silicon", model_id="bge-large-zh", api_key="key", api_host="host",
            )),
        )
        config = ModelResolver.resolve_embedding()
        assert config is not None
        assert config.model_id == "bge-large-zh"

    def test_resolve_embedding_not_configured(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": None, "embedding_model": None,
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        config = ModelResolver.resolve_embedding()
        assert config is None


class TestResolveRerank:
    def test_resolve_rerank_success(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": None, "embedding_model": None,
                                   "rerank_model": "silicon:bge-reranker",
                                   "ocr_model": None, "extract_model": None}),
        )
        monkeypatch.setattr(
            ModelResolver, "resolve",
            staticmethod(lambda composite: MagicMock(
                provider_id="silicon", model_id="bge-reranker", api_key="key", api_host="host",
            )),
        )
        config = ModelResolver.resolve_rerank()
        assert config is not None
        assert config.model_id == "bge-reranker"

    def test_resolve_rerank_not_configured(self, monkeypatch):
        from app.algorithm.model_resolver import ModelResolver

        monkeypatch.setattr(
            ModelResolver, "get_assigned_settings",
            staticmethod(lambda: {"chat_model": None, "embedding_model": None,
                                   "rerank_model": None, "ocr_model": None, "extract_model": None}),
        )
        config = ModelResolver.resolve_rerank()
        assert config is None


# ═══════════════════════════════════════════════════════════════════
# ModelResolver singleton
# ═══════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_model_resolver_is_instance(self):
        from app.algorithm.model_resolver import model_resolver, ModelResolver
        assert isinstance(model_resolver, ModelResolver)
