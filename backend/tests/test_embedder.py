"""测试 embedder.py — 本地嵌入和远程 API 调用（async）"""
import pytest
import numpy as np


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


class TestLocalEmbed:
    """_local_embed 是同步方法"""

    def test_local_embed_dimension(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        vec = emb._local_embed("test text", dim=384)
        assert len(vec) == 384

    def test_local_embed_normalized(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        vec = emb._local_embed("hello world", dim=384)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-6

    def test_local_embed_deterministic(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        v1 = emb._local_embed("test", dim=256)
        v2 = emb._local_embed("test", dim=256)
        assert v1 == v2

    def test_local_embed_different_inputs(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        v1 = emb._local_embed("hello", dim=256)
        v2 = emb._local_embed("world", dim=256)
        assert v1 != v2

    def test_local_embed_default_dim(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        vec = emb._local_embed("test")
        assert len(vec) == 384

    def test_local_embed_empty_string(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        vec = emb._local_embed("", dim=384)
        assert len(vec) == 384
        # 空字符串无 bigram，向量全零，norm = 0.0（除零保护）
        assert all(v == 0.0 for v in vec)


class TestEmbed:
    """embed() 是 async 方法"""

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        result = await emb.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_fallback_to_local(self):
        """无 API 配置时降级到本地嵌入"""
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()  # no api_key/api_host
        result = await emb.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 384
        assert len(result[1]) == 384

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
    async def test_embed_remote_failure_fallback(self, monkeypatch):
        """远程失败时降级到本地"""
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
        result = await emb.embed(["hello"])
        assert len(result) == 1
        assert len(result[0]) == 384  # fallback to local

    def test_dimension_property(self):
        from app.algorithm.knowledge.embedder import Embedder
        emb = Embedder()
        assert isinstance(emb.dimension, int)
        assert emb.dimension > 0
