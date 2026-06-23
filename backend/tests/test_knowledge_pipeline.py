"""
测试 KnowledgePipeline — 知识库管线的编排逻辑

覆盖：
- __init__ 存储 base_id, user_id, config
- _load_model_configs 加载嵌入/重排模型配置（知识库级 → 全局 → 降级）
- process_file 解析文件返回标题和内容
- process_text 处理纯文本粘贴
- index_item 调用 retriever 索引内容
- search 调用 retriever 检索并返回结果
- DB 连接在 finally 中正确关闭
- 错误传播：任何步骤失败冒泡
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

PIPELINE_PATH = "app.algorithm.knowledge.pipeline"


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Mock database connection with controllable return values."""
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    db.execute.return_value.fetchall.return_value = []
    return db


@pytest.fixture
def pipeline():
    """Basic KnowledgePipeline instance."""
    from app.algorithm.knowledge.pipeline import KnowledgePipeline

    return KnowledgePipeline(user_id=1, base_id="base-1")


# ─── __init__ ─────────────────────────────────────────────────


def test_init_stores_attributes(pipeline):
    """__init__ 正确存储 user_id, base_id。"""
    assert pipeline.user_id == 1
    assert pipeline.base_id == "base-1"
    assert pipeline._embedder_config is None
    assert pipeline._reranker_config is None


def test_init_default_base_id():
    """base_id 默认为 'default'。"""
    from app.algorithm.knowledge.pipeline import KnowledgePipeline

    p = KnowledgePipeline(user_id=1)
    assert p.base_id == "default"
    assert p.user_id == 1


# ─── _load_model_configs ──────────────────────────────────────


@pytest.mark.asyncio
async def test_load_model_configs_skips_when_already_loaded(pipeline):
    """_load_model_configs 缓存后跳过。"""
    pipeline._embedder_config = {"api_key": "cached"}
    with patch("app.database.get_db") as mock_get_db:
        pipeline._load_model_configs()
        mock_get_db.assert_not_called()


@pytest.mark.asyncio
async def test_load_model_configs_loads_from_knowledge_base(mock_db):
    """base_id 非 default 时从 knowledge_bases 表加载模型配置。"""
    # Mock DB returns embedding_model_id and rerank_model_id
    mock_db.execute.return_value.fetchone.return_value = {
        "embedding_model_id": "silicon:BAAI/bge-large-zh-v1.5",
        "rerank_model_id": "silicon:BAAI/bge-reranker-v2-m3",
    }
    mock_db.close = MagicMock()

    with patch("app.database.get_db", return_value=mock_db):
        with patch(f"{PIPELINE_PATH}.ModelRuntime.resolve_embedding") as mock_resolve_emb:
            mock_cfg = MagicMock()
            mock_cfg.api_key = "emb_key"
            mock_cfg.api_host = "https://emb.example.com"
            mock_cfg.model = "BAAI/bge-large-zh-v1.5"
            mock_cfg.provider_id = "silicon"
            mock_resolve_emb.return_value = mock_cfg

            with patch(f"{PIPELINE_PATH}.ModelRuntime.resolve_rerank") as mock_resolve_rerank:
                mock_rcfg = MagicMock()
                mock_rcfg.api_key = "rerank_key"
                mock_rcfg.api_host = "https://rerank.example.com"
                mock_rcfg.model = "BAAI/bge-reranker-v2-m3"
                mock_rcfg.provider_id = "silicon"
                mock_resolve_rerank.return_value = mock_rcfg

                from app.algorithm.knowledge.pipeline import KnowledgePipeline

                p = KnowledgePipeline(user_id=1, base_id="base-1")
                p._load_model_configs()

    assert p._embedder_config is not None
    assert p._embedder_config["api_key"] == "emb_key"
    assert p._reranker_config is not None
    assert p._reranker_config["api_key"] == "rerank_key"
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_load_model_configs_falls_back_to_global(mock_db):
    """knowledge_base 无配置时回退到全局 model_resolver。"""
    mock_db.execute.return_value.fetchone.return_value = {
        "embedding_model_id": None,
        "rerank_model_id": None,
    }
    mock_db.close = MagicMock()

    with patch("app.database.get_db", return_value=mock_db):
        with patch("app.algorithm.model_resolver.model_resolver") as mock_resolver:
            mock_cfg = MagicMock()
            mock_cfg.api_key = "global_key"
            mock_cfg.api_host = "https://global.example.com"
            mock_cfg.model_id = "global-embed-model"
            mock_cfg.provider_id = "global"
            mock_resolver.resolve_embedding.return_value = mock_cfg
            mock_resolver.resolve_rerank.return_value = None

            with patch(f"{PIPELINE_PATH}.ModelRuntime.resolve_first_rerank") as mock_first:
                mock_first_cfg = MagicMock()
                mock_first_cfg.api_key = "first_key"
                mock_first_cfg.api_host = "https://first.example.com"
                mock_first_cfg.model = "first-rerank"
                mock_first_cfg.provider_id = "first"
                mock_first.return_value = mock_first_cfg

                from app.algorithm.knowledge.pipeline import KnowledgePipeline as KP

                p = KP(user_id=1, base_id="default")
                p._load_model_configs()

    assert p._embedder_config is not None
    assert p._embedder_config["api_key"] == "global_key"
    assert p._reranker_config is not None
    assert p._reranker_config["api_key"] == "first_key"


# ─── process_file ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_file_returns_parsed_content(pipeline):
    """process_file 调用 parse_file 返回标题和内容。"""
    with patch(f"{PIPELINE_PATH}.parse_file") as mock_parse:
        mock_parse.return_value = {"title": "测试文档", "content": "文档内容", "type": "text"}
        result = await pipeline.process_file("/tmp/test.txt", "test.txt")

    assert result["title"] == "测试文档"
    assert result["content"] == "文档内容"
    assert result["type"] == "text"


@pytest.mark.asyncio
async def test_process_file_fallback_title(pipeline):
    """parse_file 无标题时使用文件名。"""
    with patch(f"{PIPELINE_PATH}.parse_file") as mock_parse:
        mock_parse.return_value = {"title": None, "content": "内容", "type": "text"}
        result = await pipeline.process_file("/tmp/unknown.txt", "unknown.txt")

    assert result["title"] == "unknown.txt"


# ─── process_text ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_text_returns_text_content(pipeline):
    """process_text 直接返回传入的标题和内容。"""
    result = await pipeline.process_text("笔记标题", "笔记内容", doc_type="note")
    assert result["title"] == "笔记标题"
    assert result["content"] == "笔记内容"
    assert result["type"] == "note"


@pytest.mark.asyncio
async def test_process_text_default_type(pipeline):
    """process_text 默认 doc_type 为 text。"""
    result = await pipeline.process_text("title", "content")
    assert result["type"] == "text"


# ─── index_item ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_item_calls_retriever(pipeline):
    """index_item 调用 get_retriever 并返回分块数。"""
    with patch.object(pipeline, "_load_model_configs") as mock_load:
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.index_item = AsyncMock(return_value=5)
            mock_get_ret.return_value = mock_retriever

            result = await pipeline.index_item("item-1", "索引内容")

    assert result == 5
    mock_load.assert_called_once()
    mock_retriever.index_item.assert_awaited_once_with("base-1", "item-1", "索引内容")


@pytest.mark.asyncio
async def test_index_item_propagates_error(pipeline):
    """index_item 异常冒泡。"""
    with patch.object(pipeline, "_load_model_configs"):
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.index_item = AsyncMock(side_effect=RuntimeError("API 失败"))
            mock_get_ret.return_value = mock_retriever

            with pytest.raises(RuntimeError, match="API 失败"):
                await pipeline.index_item("item-1", "内容")


# ─── search ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_results(pipeline):
    """search 调用 retriever.search 并返回结果列表。"""
    mock_results = [{"text": "结果1", "score": 0.9}, {"text": "结果2", "score": 0.8}]

    with patch.object(pipeline, "_load_model_configs"):
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.search = AsyncMock(return_value=mock_results)
            mock_get_ret.return_value = mock_retriever

            with patch("app.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.execute.return_value.fetchall.return_value = [
                    {"key": "search_mode", "value": "vector"},
                    {"key": "document_count", "value": "10"},
                ]
                mock_db.close = MagicMock()
                mock_get_db.return_value = mock_db

                results = await pipeline.search("test query", top_k=5, use_rerank=False)

    assert len(results) == 2
    assert results[0]["text"] == "结果1"


@pytest.mark.asyncio
async def test_search_filters_by_threshold(pipeline):
    """search 按阈值过滤低分结果。"""
    mock_results = [
        {"text": "高相关", "score": 0.9},
        {"text": "低相关", "score": 0.1},
    ]

    with patch.object(pipeline, "_load_model_configs"):
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.search = AsyncMock(return_value=mock_results)
            mock_get_ret.return_value = mock_retriever

            with patch("app.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.execute.return_value.fetchall.return_value = [
                    {"key": "threshold", "value": "0.5"},
                    {"key": "search_mode", "value": "vector"},
                    {"key": "document_count", "value": "10"},
                ]
                mock_db.close = MagicMock()
                mock_get_db.return_value = mock_db

                results = await pipeline.search("query", top_k=5, use_rerank=False)

    assert len(results) == 1
    assert results[0]["text"] == "高相关"


@pytest.mark.asyncio
async def test_search_returns_empty_on_exception(pipeline):
    """search 在异常时返回空列表而非抛出。"""
    with patch.object(pipeline, "_load_model_configs"):
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.search = AsyncMock(side_effect=RuntimeError("检索失败"))
            mock_get_ret.return_value = mock_retriever

            with patch("app.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.execute.return_value.fetchall.return_value = [
                    {"key": "search_mode", "value": "vector"},
                    {"key": "document_count", "value": "10"},
                ]
                mock_db.close = MagicMock()
                mock_get_db.return_value = mock_db

                results = await pipeline.search("query", top_k=5, use_rerank=False)

    assert results == []


@pytest.mark.asyncio
async def test_search_with_rerank(pipeline):
    """search 当 use_rerank=True 且配置了重排器时使用 search_with_rerank。"""
    pipeline._reranker_config = {"api_key": "key", "api_host": "host", "model": "model"}

    with patch.object(pipeline, "_load_model_configs"):
        with patch("app.algorithm.knowledge.retriever.get_retriever") as mock_get_ret:
            mock_retriever = AsyncMock()
            mock_retriever.search_with_rerank = AsyncMock(return_value=[{"text": "reranked"}])
            mock_get_ret.return_value = mock_retriever

            with patch("app.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.execute.return_value.fetchall.return_value = []
                mock_db.close = MagicMock()
                mock_get_db.return_value = mock_db

                results = await pipeline.search("query", top_k=5, use_rerank=True)

    assert len(results) == 1
    mock_retriever.search_with_rerank.assert_awaited_once()


# ─── DB 连接管理 ──────────────────────────────────────────────


def test_load_model_configs_closes_db(mock_db):
    """_load_model_configs 在 finally 中关闭 DB 连接（即使异常也关闭）。"""
    from app.algorithm.knowledge.pipeline import KnowledgePipeline

    mock_db.close = MagicMock()
    mock_db.execute.side_effect = RuntimeError("DB error")

    with patch("app.database.get_db", return_value=mock_db):
        p = KnowledgePipeline(user_id=1, base_id="base-1")
        with pytest.raises(RuntimeError, match="DB error"):
            p._load_model_configs()

    # DB 连接仍然被关闭（finally 块保证）
    mock_db.close.assert_called_once()


# ─── get_embedding_api_config ─────────────────────────────────


def test_get_embedding_api_config_returns_empty_when_no_row():
    """get_embedding_api_config 无数据时返回空字典。"""
    from app.algorithm.knowledge.pipeline import get_embedding_api_config

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchone.return_value = None
    mock_db.close = MagicMock()

    with patch("app.database.get_db", return_value=mock_db):
        result = get_embedding_api_config("silicon")

    assert result == {}
    mock_db.close.assert_called_once()


def test_get_embedding_api_config_returns_empty_no_api_key():
    """get_embedding_api_config 无 API key 时返回空字典。"""
    from app.algorithm.knowledge.pipeline import get_embedding_api_config

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchone.return_value = {
        "api_host": "https://api.example.com",
        "api_model": "BAAI/bge-large-zh-v1.5",
        "models": json.dumps([{"id": "BAAI/bge-large-zh-v1.5"}]),
    }
    mock_db.close = MagicMock()

    with patch("app.database.get_db", return_value=mock_db):
        with patch("app.algorithm.model_service._get_provider_api_key", return_value=""):
            result = get_embedding_api_config("silicon")

    assert result == {}
