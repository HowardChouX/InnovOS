"""测试 embedder.py — 远程 API 调用（async）"""
import pytest


class TestEmbedderInit:
    def test_default_init(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        assert emb.model == "BAAI/bge-large-zh-v1.5"
        assert emb.dimension == 1024
        assert emb.api_key == ""
        assert emb.api_host == ""

    def test_custom_init(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder(
            api_key="sk-test",
            api_host="https://api.test.com",
            model="text-embedding-3-small",
        )
        assert emb.api_key == "sk-test"
        assert emb.api_host == "https://api.test.com"
        assert emb.model == "text-embedding-3-small"


class TestEmbed:
    """embed() 是 async 方法"""

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        result = await emb.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_no_api_raises(self):
        """无 API 配置时抛出 RuntimeError"""
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()  # no api_key/api_host
        with pytest.raises(RuntimeError, match="未配置嵌入模型 API"):
            await emb.embed(["hello", "world"])

    @pytest.mark.asyncio
    async def test_embed_remote_success(self, monkeypatch):
        """有 API 配置时调用远程 API"""
        from app.algorithm.knowledge.embedder import Embedder

        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "data": [
                        {"embedding": [0.1] * 384, "index": 0},
                        {"embedding": [0.2] * 384, "index": 1},
                    ]
                }

        class MockAsyncClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, *a, **kw):
                return MockResponse()

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
        emb = Embedder(api_key="sk-test", api_host="https://api.test.com")
        result = await emb.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 384
        assert result[0] != result[1]  # different embeddings

    @pytest.mark.asyncio
    async def test_embed_remote_failure_propagates(self, monkeypatch):
        """远程失败时异常冒泡（无降级）"""
        from app.algorithm.knowledge.embedder import Embedder

        class FailingAsyncClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, *a, **kw):
                raise Exception("Connection failed")

        monkeypatch.setattr("httpx.AsyncClient", FailingAsyncClient)
        emb = Embedder(api_key="sk-test", api_host="https://api.test.com")
        with pytest.raises(Exception, match="Connection failed"):
            await emb.embed(["hello"])

    def test_dimension_property(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        assert isinstance(emb.dimension, int)
        assert emb.dimension > 0
