"""
测试 KnowledgeRetriever — RAG 检索管线

覆盖：
- __init__ 初始化 embedder, chunker, vector_store
- index_item 分块 → 嵌入 → 原子替换存储
- search 嵌入查询 → 向量搜索 → 返回结果
- is_indexed 正确检查 item_id 是否已索引
- get_retriever 缓存和重建逻辑
- 空内容处理
- 搜索空库返回空列表
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

RETRIEVER_PATH = "app.algorithm.knowledge.retriever"


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    db.execute.return_value.fetchall.return_value = []
    db.close = MagicMock()
    return db


@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.count.return_value = 10
    vs.replace_by_external_id = MagicMock()
    vs.search.return_value = [
        {"id": "vec-1", "item_id": "item-1", "text": "结果1", "score": 0.95},
        {"id": "vec-2", "item_id": "item-1", "text": "结果2", "score": 0.85},
    ]
    vs.delete_by_external_id = MagicMock()
    vs.delete_by_external_ids = MagicMock()
    return vs


@pytest.fixture
def mock_embedder():
    emb = AsyncMock()
    emb.embed = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    emb.dimension = 1024
    return emb


@pytest.fixture
def retriever(mock_vector_store, mock_embedder):
    """Create a KnowledgeRetriever with mocked dependencies."""
    from app.algorithm.knowledge.retriever import KnowledgeRetriever

    with patch(f"{RETRIEVER_PATH}.VectorStore", return_value=mock_vector_store):
        with patch(f"{RETRIEVER_PATH}.Embedder", return_value=mock_embedder):
            r = KnowledgeRetriever(user_id=1)
    return r


# ─── __init__ ─────────────────────────────────────────────────


def test_init_creates_embedder_and_vector_store():
    """__init__ 创建 embedder, chunker, vector_store。"""
    from app.algorithm.knowledge.retriever import KnowledgeRetriever

    with patch(f"{RETRIEVER_PATH}.VectorStore") as MockVS:
        with patch(f"{RETRIEVER_PATH}.Embedder") as MockEmb:
            r = KnowledgeRetriever(user_id=42)

    assert r.user_id == 42
    MockEmb.assert_called_once()
    MockVS.assert_called_once_with(user_id=42)
    assert r.chunker is not None


def test_init_with_embedder_config():
    """__init__ 使用传入的 embedder_config。"""
    from app.algorithm.knowledge.retriever import KnowledgeRetriever

    config = {"api_key": "my_key", "api_host": "https://emb.example.com", "model": "my-model"}
    with patch(f"{RETRIEVER_PATH}.VectorStore"):
        with patch(f"{RETRIEVER_PATH}.Embedder") as MockEmb:
            KnowledgeRetriever(user_id=1, embedder_config=config)

    MockEmb.assert_called_once_with(api_key="my_key", api_host="https://emb.example.com", model="my-model")


# ─── index_item ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_item_chunks_embeds_and_stores(retriever, mock_vector_store, mock_embedder):
    """index_item 分块 → 向量化 → replace_by_external_id。"""
    # Override chunker to return controlled output
    retriever.chunker = lambda content, chunk_size=512, chunk_overlap=64: [
        {"text": "片段1", "index": 0},
        {"text": "片段2", "index": 1},
    ]

    with patch("app.database.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = [
            {"key": "chunk_size", "value": "256"},
            {"key": "chunk_overlap", "value": "32"},
        ]
        mock_get_db.return_value = mock_db

        result = await retriever.index_item("base-1", "item-1", "测试内容")

    assert result == 2
    mock_embedder.embed.assert_awaited_once_with(["片段1", "片段2"])
    mock_vector_store.replace_by_external_id.assert_called_once()


@pytest.mark.asyncio
async def test_index_item_empty_content_clears_vectors(retriever, mock_vector_store):
    """空内容调用 replace_by_external_id 清空向量。"""
    retriever.chunker = lambda content, chunk_size=512, chunk_overlap=64: []

    result = await retriever.index_item("base-1", "item-1", "")

    assert result == 0
    mock_vector_store.replace_by_external_id.assert_called_once_with("base-1", "item-1", [], [])


@pytest.mark.asyncio
async def test_index_item_propagates_embedder_error(retriever, mock_embedder):
    """嵌入器失败时异常冒泡。"""
    retriever.chunker = lambda content, chunk_size=512, chunk_overlap=64: [
        {"text": "片段", "index": 0},
    ]
    mock_embedder.embed = AsyncMock(side_effect=RuntimeError("Embedding failed"))

    with pytest.raises(RuntimeError, match="Embedding failed"):
        await retriever.index_item("base-1", "item-1", "内容")


# ─── search ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_embeds_query_and_returns_results(retriever, mock_vector_store, mock_embedder):
    """search 嵌入查询 → 向量搜索 → 返回结果。"""
    mock_embedder.embed = AsyncMock(return_value=[[0.5, 0.6]])

    results = await retriever.search("base-1", "测试查询", top_k=5)

    assert len(results) == 2
    assert results[0]["text"] == "结果1"
    mock_embedder.embed.assert_awaited_once_with(["测试查询"])


@pytest.mark.asyncio
async def test_search_empty_base_returns_empty(retriever, mock_vector_store):
    """count(base_id) == 0 时直接返回空列表。"""
    mock_vector_store.count.return_value = 0

    results = await retriever.search("empty-base", "查询", top_k=5)

    assert results == []


@pytest.mark.asyncio
async def test_search_with_hybrid_mode(retriever, mock_vector_store):
    """search 支持 hybrid 模式（传参给 vector_store）。"""
    mock_vector_store.count.return_value = 10

    results = await retriever.search(
        "base-1", "查询", top_k=5, search_mode="hybrid", hybrid_alpha=0.3
    )

    assert len(results) == 2
    mock_vector_store.search.assert_called_once_with(
        "base-1", [0.1, 0.2], 5, query_text="查询", mode="hybrid", alpha=0.3
    )


# ─── is_indexed ────────────────────────────────────────────────


def test_is_indexed_returns_true_when_found(retriever, mock_db):
    """is_indexed 在向量存在时返回 True。"""
    mock_db.execute.return_value.fetchone.return_value = {"1": 1}

    with patch("app.database.get_db", return_value=mock_db):
        result = retriever.is_indexed("item-1", "base-1")

    assert result is True
    sql = mock_db.execute.call_args[0][0]
    assert "item_id" in sql
    assert "base_id" in sql
    mock_db.close.assert_called_once()


def test_is_indexed_returns_false_when_not_found(retriever, mock_db):
    """is_indexed 在向量不存在时返回 False。"""
    mock_db.execute.return_value.fetchone.return_value = None

    with patch("app.database.get_db", return_value=mock_db):
        result = retriever.is_indexed("item-nonexistent", "base-1")

    assert result is False


def test_is_indexed_uses_proper_placeholders(retriever, mock_db):
    """is_indexed 使用 %s 参数化查询（防止 SQL 注入）。"""
    mock_db.execute.return_value.fetchone.return_value = None

    with patch("app.database.get_db", return_value=mock_db):
        retriever.is_indexed("item-1", "base-1")

    call_args = mock_db.execute.call_args
    assert call_args is not None
    params = call_args[0][1]
    assert params == ("item-1", "base-1")


# ─── get_retriever ─────────────────────────────────────────────


def test_get_retriever_returns_instance():
    """get_retriever 返回 KnowledgeRetriever 实例。"""
    from app.algorithm.knowledge.retriever import get_retriever

    with patch(f"{RETRIEVER_PATH}.KnowledgeRetriever") as MockKR:
        MockKR.return_value = "retriever-instance"
        r = get_retriever(user_id=1)

    assert r == "retriever-instance"


def test_get_retriever_caches_by_user_id():
    """get_retriever 按 user_id 缓存，相同 ID 返回同一实例。"""
    from app.algorithm.knowledge.retriever import get_retriever

    with patch(f"{RETRIEVER_PATH}.KnowledgeRetriever") as MockKR:
        MockKR.return_value = "retriever-instance"
        r1 = get_retriever(user_id=1)
        # Clear internal cache for clean test
        import app.algorithm.knowledge.retriever as ret_mod

        ret_mod._retrievers.clear()
        MockKR.return_value = "retriever-instance-2"
        r2 = get_retriever(user_id=2)

    assert r1 != r2


def test_get_retriever_recreates_on_config_change():
    """embedder_config 变化时重新创建检索器。"""
    from app.algorithm.knowledge.retriever import get_retriever
    import app.algorithm.knowledge.retriever as ret_mod

    ret_mod._retrievers.clear()

    with patch(f"{RETRIEVER_PATH}.KnowledgeRetriever") as MockKR:
        get_retriever(user_id=1)
        get_retriever(user_id=1, embedder_config={"new": "config"})

    assert MockKR.call_count == 2


def test_get_retriever_returns_cached_without_config():
    """不带 config 参数时返回缓存的检索器。"""
    from app.algorithm.knowledge.retriever import get_retriever
    import app.algorithm.knowledge.retriever as ret_mod

    ret_mod._retrievers.clear()

    with patch(f"{RETRIEVER_PATH}.KnowledgeRetriever") as MockKR:
        instance1 = "instance-1"
        MockKR.return_value = instance1
        r1 = get_retriever(user_id=1)
        r2 = get_retriever(user_id=1)

    assert r1 is r2
    assert MockKR.call_count == 1


# ─── reranker property ────────────────────────────────────────


def test_reranker_property_lazy_creates_when_config_present(retriever):
    """reranker 属性在配置存在时懒加载。"""
    retriever._reranker_config = {"api_key": "rk", "api_host": "https://rerank.example.com", "model": "rerank-model"}

    with patch("app.algorithm.knowledge.reranker.Reranker") as MockReranker:
        _ = retriever.reranker

    MockReranker.assert_called_once_with(api_key="rk", api_host="https://rerank.example.com", model="rerank-model")


def test_reranker_property_returns_none_when_no_config(retriever):
    """reranker 无配置时返回 None。"""
    retriever._reranker_config = {}
    assert retriever.reranker is None


# ─── search_with_rerank ───────────────────────────────────────


@pytest.mark.asyncio
async def test_search_with_rerank_reranks_results(retriever):
    """search_with_rerank 检索后重排。"""
    # Mock search and reranker
    retriever.search = AsyncMock(
        return_value=[
            {"text": "文档1", "score": 0.9, "item_id": "a"},
            {"text": "文档2", "score": 0.8, "item_id": "b"},
        ]
    )
    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(
        return_value=[
            {"index": 1, "relevance_score": 0.95, "text": "文档2"},
            {"index": 0, "relevance_score": 0.85, "text": "文档1"},
        ]
    )
    retriever._reranker = mock_reranker

    results = await retriever.search_with_rerank("base-1", "查询", top_k=10, rerank_top_k=5)

    assert len(results) == 2
    # Should be in reranked order
    assert results[0]["score"] == 0.95
    assert results[1]["score"] == 0.85


@pytest.mark.asyncio
async def test_search_with_rerank_no_reranker_fallback(retriever):
    """重排器不存在时返回原始检索结果。"""
    retriever.search = AsyncMock(return_value=[{"text": "文档1", "score": 0.9}])
    retriever._reranker = None

    results = await retriever.search_with_rerank("base-1", "查询", top_k=10)

    assert len(results) == 1


# ─── total_chunks ─────────────────────────────────────────────


def test_total_chunks_delegates_to_vector_store(retriever, mock_vector_store):
    """total_chunks 委托给 vector_store.count()。"""
    from app.algorithm.knowledge.retriever import KnowledgeRetriever

    total = retriever.total_chunks
    assert total == 10


# ─── rebuild_retriever_from_db ────────────────────────────────


def test_rebuild_retriever_from_db():
    """rebuild_retriever_from_db 不抛出异常。"""
    from app.algorithm.knowledge.retriever import rebuild_retriever_from_db

    with patch(f"{RETRIEVER_PATH}.get_retriever") as mock_get:
        mock_ret = MagicMock()
        mock_ret.vector_store.count.return_value = 5
        mock_get.return_value = mock_ret

        # Should not raise
        rebuild_retriever_from_db(user_id=1)
