"""测试 model_runtime.py — 能力解析与连接测试"""
import pytest
from unittest.mock import MagicMock


class TestParseModelId:
    def test_simple_model_id(self):
        from app.algorithm.model_runtime import ModelRuntime
        provider, model = ModelRuntime.parse_model_id("gpt-4")
        assert provider == ""
        assert model == "gpt-4"

    def test_composite_model_id(self):
        from app.algorithm.model_runtime import ModelRuntime
        provider, model = ModelRuntime.parse_model_id("silicon:BAAI/bge-large-zh-v1.5")
        assert provider == "silicon"
        assert model == "BAAI/bge-large-zh-v1.5"

    def test_empty_string(self):
        from app.algorithm.model_runtime import ModelRuntime
        provider, model = ModelRuntime.parse_model_id("")
        assert provider == ""
        assert model == ""

    def test_none_string(self):
        from app.algorithm.model_runtime import ModelRuntime
        provider, model = ModelRuntime.parse_model_id(None)
        assert provider == ""
        assert model == ""

    def test_with_colon_prefix(self):
        from app.algorithm.model_runtime import ModelRuntime
        provider, model = ModelRuntime.parse_model_id("openai:text-embedding-3-small")
        assert provider == "openai"
        assert model == "text-embedding-3-small"


class TestResolveEmbedding:
    def test_resolve_with_provider(self, monkeypatch):
        """指定 provider 时应查该供应商"""
        from app.algorithm.model_runtime import ModelRuntime

        mock_row = {
            "api_host": "https://api.openai.com",
            "api_key_encrypted": "key_openai",
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")

        result = ModelRuntime.resolve_embedding("openai:text-embedding-3-small")
        assert result is not None
        assert result.api_key == "decrypted_key_openai"
        assert result.model == "text-embedding-3-small"
        assert result.provider_id == "openai"

    def test_resolve_empty_model_id(self):
        from app.algorithm.model_runtime import ModelRuntime
        result = ModelRuntime.resolve_embedding("")
        assert result is None


class TestResolveFirstEmbedding:
    def test_finds_first_embedding(self, monkeypatch, sample_provider_rows):
        """应在启用的供应商中找到第一个有 embedding 模型的"""
        from app.algorithm.model_runtime import ModelRuntime

        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = sample_provider_rows
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")

        result = ModelRuntime.resolve_first_embedding()
        assert result is not None
        assert result.model == "BAAI/bge-large-zh-v1.5"
        assert result.provider_id == "silicon"

    def test_no_enabled_providers(self, monkeypatch):
        """没有启用的供应商应返回 None"""
        from app.algorithm.model_runtime import ModelRuntime

        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        result = ModelRuntime.resolve_first_embedding()
        assert result is None


class TestResolveFirstRerank:
    def test_finds_first_rerank(self, monkeypatch):
        """找到第一个有 rerank 模型的供应商"""
        from app.algorithm.model_runtime import ModelRuntime

        rows = [
            {
                "provider_id": "test_provider",
                "api_host": "https://api.test.com",
                "api_key_encrypted": "key_test",
                "models": '[{"id": "rerank-model", "capabilities": ["rerank"]}]',
                "is_enabled": 1,
                "priority": 1,
            },
        ]
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")

        result = ModelRuntime.resolve_first_rerank()
        assert result is not None
        assert result.model == "rerank-model"


class TestTestConnection:
    def test_provider_not_found(self, monkeypatch):
        """找不到供应商应返回 error"""
        from app.algorithm.model_runtime import ModelRuntime

        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)

        result = ModelRuntime.test_connection("nonexistent", "gpt-4")
        assert result["status"] == "error"

    def test_routes_to_embedding_by_capability(self, monkeypatch):
        """embedding capability 应路由到嵌入测试"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.openai.com",
            "api_key_encrypted": "key_openai",
            "models": '[{"id": "text-embedding-3-small", "capabilities": ["embedding"]}]',
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")
        # mock _test_embedding to avoid real API call
        monkeypatch.setattr(ModelRuntime, "_test_embedding", lambda ak, ah, m: {
            "status": "ok", "model": m, "type": "embedding", "dimension": 384
        })

        result = ModelRuntime.test_connection("test", "text-embedding-3-small")
        assert result["status"] == "ok"
        assert result["type"] == "embedding"

    def test_routes_to_rerank_by_capability(self, monkeypatch):
        """rerank capability 应路由到重排测试"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.test.com",
            "api_key_encrypted": "key_test",
            "models": '[{"id": "rerank-model", "capabilities": ["rerank"]}]',
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")
        monkeypatch.setattr(ModelRuntime, "_test_rerank", lambda ak, ah, m: {
            "status": "ok", "model": m, "type": "rerank"
        })

        result = ModelRuntime.test_connection("test", "rerank-model")
        assert result["status"] == "ok"
        assert result["type"] == "rerank"

    def test_routes_to_chat_by_default(self, monkeypatch):
        """没有 embedding/rerank 标记的应路由到聊天测试"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.test.com",
            "api_key_encrypted": "key_test",
            "models": '[{"id": "gpt-4o", "capabilities": ["chat"]}]',
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")
        monkeypatch.setattr(ModelRuntime, "_test_chat", lambda ak, ah, m: {
            "status": "ok", "model": m, "type": "chat"
        })

        result = ModelRuntime.test_connection("test", "gpt-4o")
        assert result["status"] == "ok"
        assert result["type"] == "chat"

    def test_uses_registry_fallback(self, monkeypatch, registry):
        """存储在 models 未找到时，应在注册表查找"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.test.com",
            "api_key_encrypted": "key_test",
            "models": '[]',  # empty models list
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")
        monkeypatch.setattr(ModelRuntime, "_test_embedding", lambda ak, ah, m: {
            "status": "ok", "model": m, "type": "embedding"
        })

        # text-embedding-3-small is known to registry as embedding
        result = ModelRuntime.test_connection("test", "text-embedding-3-small")
        assert result["status"] == "ok"

    def test_infer_capabilities_fallback(self, monkeypatch):
        """注册表也未找到时，应使用正则推断"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.test.com",
            "api_key_encrypted": "key_test",
            "models": '[]',
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")
        monkeypatch.setattr(ModelRuntime, "_test_chat", lambda ak, ah, m: {
            "status": "ok", "model": m, "type": "chat"
        })

        # 未知但显然不是 embedding/rerank 的模型 → chat
        result = ModelRuntime.test_connection("test", "some-unknown-chat-model")
        assert result["status"] == "ok"
        assert result["type"] == "chat"

    def test_exception_handling(self, monkeypatch):
        """测试异常时返回 error 消息"""
        from app.algorithm.model_runtime import ModelRuntime

        row = {
            "api_host": "https://api.test.com",
            "api_key_encrypted": "key_test",
            "models": '[{"id": "chat-model", "capabilities": ["chat"]}]',
        }
        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")

        def failing_test(*a, **kw):
            raise RuntimeError("API connection refused")

        monkeypatch.setattr(ModelRuntime, "_test_chat", failing_test)
        result = ModelRuntime.test_connection("test", "chat-model")
        assert result["status"] == "error"
        assert "API connection refused" in result["message"]


class TestResolve:
    def test_resolve_without_provider_finds_first(self, monkeypatch, sample_provider_rows):
        """不指定 provider 时应遍历所有启用的供应商"""
        from app.algorithm.model_runtime import ModelRuntime

        mock_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = sample_provider_rows
        cursor.fetchone.return_value = sample_provider_rows[0]
        mock_conn.execute.return_value = cursor
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
        monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}")

        result = ModelRuntime._resolve("", "BAAI/bge-large-zh-v1.5")
        assert result is not None
        assert result.provider_id == "silicon"
        assert result.model == "BAAI/bge-large-zh-v1.5"
