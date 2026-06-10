"""测试 api/models.py — 能力筛选 API（集成测试）"""
import json
import pytest


class TestListEmbeddingModels:
    """GET /api/models/embedding"""

    def test_status_200(self, mock_db_all_providers, client):
        resp = client.get("/api/models/embedding")
        assert resp.status_code == 200

    def test_returns_data_and_message(self, mock_db_all_providers, client):
        resp = client.get("/api/models/embedding")
        data = resp.json()
        assert "data" in data
        assert "message" in data
        assert isinstance(data["data"], list)

    def test_items_have_required_fields(self, mock_db_all_providers, client):
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        assert len(items) > 0
        item = items[0]
        assert "id" in item
        assert "providerId" in item
        assert "providerName" in item
        assert "modelId" in item
        assert "label" in item

    def test_filters_only_embedding_models(self, mock_db_all_providers, client):
        """不应包含 chat-only 模型"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        model_ids = [i["modelId"] for i in items]
        # chat-only models should not appear
        assert "deepseek-ai/DeepSeek-V3" not in model_ids
        assert "gpt-4o" not in model_ids
        # embedding models should appear
        assert "BAAI/bge-large-zh-v1.5" in model_ids
        assert "text-embedding-3-small" in model_ids

    def test_rerank_models_excluded(self, mock_db_all_providers, client):
        """重排模型不应出现在嵌入列表中"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        model_ids = [i["modelId"] for i in items]
        assert "BAAI/bge-reranker-v2-m3" not in model_ids

    def test_id_format_is_providerid_modelid(self, mock_db_all_providers, client):
        """id 格式应为 {providerId}::{modelId}"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        for item in items:
            assert "::" in item["id"]

    def test_disabled_provider_excluded(self, mock_db_all_providers, client):
        """disabled_provider 的模型不应出现"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        provider_ids = {i["providerId"] for i in items}
        assert "disabled_provider" not in provider_ids

    def test_label_format(self, mock_db_all_providers, client):
        """label 应包含模型名和供应商名"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        for item in items:
            assert " · " in item["label"]


class TestListRerankModels:
    """GET /api/models/rerank"""

    def test_status_200(self, mock_db_all_providers, client):
        resp = client.get("/api/models/rerank")
        assert resp.status_code == 200

    def test_returns_data_and_message(self, mock_db_all_providers, client):
        resp = client.get("/api/models/rerank")
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_items_have_required_fields(self, mock_db_all_providers, client):
        resp = client.get("/api/models/rerank")
        items = resp.json()["data"]
        assert len(items) > 0
        item = items[0]
        assert "id" in item
        assert "modelId" in item
        assert "label" in item

    def test_filters_only_rerank_models(self, mock_db_all_providers, client):
        """只返回有 rerank capability 的模型"""
        resp = client.get("/api/models/rerank")
        items = resp.json()["data"]
        model_ids = [i["modelId"] for i in items]
        assert "BAAI/bge-reranker-v2-m3" in model_ids
        assert "BAAI/bge-large-zh-v1.5" not in model_ids  # embedding excluded

    def test_embedding_models_excluded(self, mock_db_all_providers, client):
        resp = client.get("/api/models/rerank")
        items = resp.json()["data"]
        model_ids = [i["modelId"] for i in items]
        assert "text-embedding-3-small" not in model_ids


class TestEmptyResults:
    """没有匹配模型时应返回空列表"""

    def test_no_rerank_models_in_empty_database(self, client):
        """没有配置任何 provider 时 rerank 列表为空"""
        resp = client.get("/api/models/rerank")
        items = resp.json()["data"]
        assert items == []

    def test_no_embedding_models_in_empty_database(self, client):
        """没有配置任何 provider 时 embedding 列表为空"""
        resp = client.get("/api/models/embedding")
        items = resp.json()["data"]
        assert items == []
