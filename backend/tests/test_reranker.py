"""测试 reranker.py — 重排模型三种 provider 格式（async）"""
import pytest


class TestRerankerInit:
    def test_default_init(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker()
        assert r.model == "BAAI/bge-reranker-v2-m3"
        assert r.api_key == ""
        assert r.api_host == ""

    def test_custom_init(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(api_key="sk-test", api_host="https://api.test.com", model="rerank-model")
        assert r.api_key == "sk-test"
        assert r.api_host == "https://api.test.com"
        assert r.model == "rerank-model"


class TestDetectProvider:
    def test_detect_dashscope(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(api_host="https://dashscope.aliyuncs.com")
        assert r._detect_provider() == "dashscope"

    def test_detect_aliyun(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(api_host="https://api.aliyuncs.com")
        assert r._detect_provider() == "dashscope"

    def test_detect_openai(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(api_host="https://api.siliconflow.cn")
        assert r._detect_provider() == "openai"

    def test_detect_empty_host(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker()
        assert r._detect_provider() == "openai"

    def test_detect_via_endpoint_type_tei(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(endpoint_type="tei")
        assert r._detect_provider() == "tei"

    def test_detect_via_endpoint_type_jina(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(endpoint_type="jina-rerank")
        assert r._detect_provider() == "jina"

    def test_detect_via_endpoint_type_dashscope(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(endpoint_type="dashscope")
        assert r._detect_provider() == "dashscope"

    def test_detect_via_endpoint_type_default(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker(endpoint_type="openai-chat-completions")
        assert r._detect_provider() == "openai"


class TestRerankEmpty:
    @pytest.mark.asyncio
    async def test_empty_documents(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker()
        result = await r.rerank("test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from app.algorithm.knowledge.reranker import Reranker
        r = Reranker()
        result = await r.rerank("", ["doc1", "doc2"])
        assert result == []


class TestRerankRemote:
    """mock httpx.AsyncClient 测试远程调用"""

    @pytest.mark.asyncio
    async def test_openai_compat_format(self, monkeypatch):
        """OpenAI 兼容格式：POST /rerank"""
        from app.algorithm.knowledge.reranker import Reranker

        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "results": [
                        {"index": 0, "relevance_score": 0.95, "text": "doc1"},
                        {"index": 1, "relevance_score": 0.12, "text": "doc2"},
                    ]
                }

        class MockAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, url, **kw):
                return MockResp()

        monkeypatch.setattr("httpx.AsyncClient", MockAClient)
        r = Reranker(api_key="sk-test", api_host="https://api.test.com")
        result = await r.rerank("test query", ["doc1", "doc2"], top_n=2)
        assert len(result) == 2
        assert result[0]["relevance_score"] == 0.95
        assert result[1]["index"] == 1

    @pytest.mark.asyncio
    async def test_rerank_sorted_by_score(self, monkeypatch):
        """结果按 relevance_score 降序"""
        from app.algorithm.knowledge.reranker import Reranker

        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "results": [
                        {"index": 0, "relevance_score": 0.3, "text": "doc1"},
                        {"index": 1, "relevance_score": 0.9, "text": "doc2"},
                    ]
                }

        class MockAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, *a, **kw):
                return MockResp()

        monkeypatch.setattr("httpx.AsyncClient", MockAClient)
        r = Reranker(api_key="sk-test", api_host="https://api.test.com")
        result = await r.rerank("q", ["doc1", "doc2"])
        assert result[0]["relevance_score"] >= result[1]["relevance_score"]

    @pytest.mark.asyncio
    async def test_remote_failure_fallback(self, monkeypatch):
        """远程失败降级返回原始顺序"""
        from app.algorithm.knowledge.reranker import Reranker

        class FailingAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, *a, **kw):
                raise Exception("Network error")

        monkeypatch.setattr("httpx.AsyncClient", FailingAClient)
        r = Reranker(api_key="sk-test", api_host="https://api.test.com")
        result = await r.rerank("q", ["doc1", "doc2"])
        assert len(result) == 2
        assert result[0]["relevance_score"] == 0.0
        assert result[1]["relevance_score"] == 0.0


class TestDashScope:
    @pytest.mark.asyncio
    async def test_rerank_dashscope_format(self, monkeypatch):
        from app.algorithm.knowledge.reranker import Reranker

        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "output": {
                        "results": [
                            {"index": 0, "relevance_score": 0.85},
                        ]
                    }
                }

        class MockAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, url, **kw):
                return MockResp()

        monkeypatch.setattr("httpx.AsyncClient", MockAClient)
        r = Reranker(api_key="sk-test", api_host="https://dashscope.aliyuncs.com")
        result = await r.rerank("q", ["doc1"])
        assert len(result) == 1
        assert "text" in result[0]


class TestTEI:
    @pytest.mark.asyncio
    async def test_tei_array_response(self, monkeypatch):
        from app.algorithm.knowledge.reranker import Reranker

        class MockResp:
            status_code = 200
            def json(self):
                return [
                    {"index": 0, "score": 0.92, "text": "doc1"},
                    {"index": 1, "score": 0.1, "text": "doc2"},
                ]

        class MockAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, url, **kw):
                return MockResp()

        monkeypatch.setattr("httpx.AsyncClient", MockAClient)
        r = Reranker(api_key="sk-test", api_host="https://tei.api.test.com")
        result = await r.rerank("q", ["doc1", "doc2"])
        assert len(result) == 2
        assert result[0]["relevance_score"] == 0.92


class TestTopN:
    @pytest.mark.asyncio
    async def test_top_n_is_sent_to_api(self, monkeypatch):
        """top_n 参数应传递给 API body"""
        from app.algorithm.knowledge.reranker import Reranker

        sent_bodies = []

        class MockResp:
            status_code = 200
            def json(self):
                return {"results": []}

        class MockAClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a, **kw):
                pass
            async def post(self, *a, **kw):
                sent_bodies.append(kw.get("json", {}))
                return MockResp()

        monkeypatch.setattr("httpx.AsyncClient", MockAClient)
        r = Reranker(api_key="sk-test", api_host="https://api.test.com")
        await r.rerank("q", ["d1", "d2", "d3", "d4", "d5"], top_n=3)
        assert sent_bodies[0].get("top_n") == 3
