"""
PatentSearchEngine TDD 测试

覆盖：index_patent, search, delete_patent, backfill, embed_text
策略：mock Embedder（避免 API 调用），mock get_db（避免 PostgreSQL）
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── PatentSearchEngine 初始化（mock embed_text 防止 API 调用） ──

FAKE_VEC = [0.1] * 1024


@pytest.fixture
def engine():
    from app.algorithm.patent_search_engine import PatentSearchEngine

    e = PatentSearchEngine()
    # Set embed_text as an instance attribute (bypasses descriptor protocol)
    async def mock_embed_text(text):
        return FAKE_VEC

    e.embed_text = mock_embed_text
    return e


@pytest.fixture
def mock_db(monkeypatch):
    """Mock get_db 返回可控的 MagicMock"""
    conn = MagicMock()
    monkeypatch.setattr("app.database.get_db", lambda: conn)
    # The module caches 'from app.database import get_db' at import time,
    # so we must also patch the local reference.
    monkeypatch.setattr("app.algorithm.patent_search_engine.get_db", lambda: conn)
    return conn


# ═══════════════════════════════════════════════════════════════
# Test: index_patent
# ═══════════════════════════════════════════════════════════════

class TestIndexPatent:

    async def test_index_patent_stores_vector(self, engine, mock_db):
        """index_patent 应调用 INSERT 并 commit"""
        mock_db.execute.return_value.fetchone.return_value = None  # no conflict needed
        result = await engine.index_patent(1, "散热结构", "一种新型散热结构")
        assert result is True
        # 验证执行了 INSERT/upsert
        insert_sqls = [args[0] for args in mock_db.execute.call_args_list
                       if "INSERT INTO patent_vectors" in str(args[0])]
        assert len(insert_sqls) == 1
        mock_db.commit.assert_called_once()

    async def test_index_patent_empty_text_returns_false(self, engine, mock_db):
        """空文本应返回 False 且不调用数据库"""
        mock_db.reset_mock()
        result = await engine.index_patent(2, "", "")
        assert result is False
        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_index_patent_with_full_content(self, engine, mock_db):
        """index_patent_with_content 也应存储向量"""
        result = await engine.index_patent_with_content(3, "全文内容")
        assert result is True
        insert_sqls = [args[0] for args in mock_db.execute.call_args_list
                       if "INSERT INTO patent_vectors" in str(args[0])]
        assert len(insert_sqls) == 1
        mock_db.commit.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Test: delete_patent
# ═══════════════════════════════════════════════════════════════

class TestDeletePatent:

    async def test_delete_patent_executes_delete(self, engine, mock_db):
        """delete_patent 应执行 DELETE FROM patent_vectors"""
        await engine.delete_patent(1)
        delete_sqls = [args[0] for args in mock_db.execute.call_args_list
                       if "DELETE FROM patent_vectors" in str(args[0])]
        assert len(delete_sqls) == 1
        mock_db.commit.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Test: search
# ═══════════════════════════════════════════════════════════════

class TestSearch:

    async def test_search_empty_query_returns_empty(self, engine, mock_db):
        """空查询应直接返回空列表"""
        mock_db.execute.reset_mock()
        results = await engine.search("")
        assert results == []
        mock_db.execute.assert_not_called()

    async def test_search_pg_calls_operator(self, engine, mock_db):
        """PG 环境下应使用 <=> 算子"""
        # _vector_search now uses get_db() → mock_db, not raw psycopg2.connect
        row = {"id": 1, "title": "散热结构", "abstract": "摘要", "description": "",
               "patent_number": "CN123", "applicants": '["华为"]', "relevance": 0.95}
        mock_db.execute.return_value.fetchall.return_value = [row]

        results = await engine.search("散热")

        assert len(results) == 1
        assert results[0]["relevance"] == 0.95

        # 验证使用了 <=> 算子
        call_sql = mock_db.execute.call_args[0][0]
        assert "<->" in call_sql or "<=>" in call_sql


# ═══════════════════════════════════════════════════════════════
# Test: backfill
# ═══════════════════════════════════════════════════════════════

class TestBackfill:

    async def test_backfill_skips_existing(self, engine, mock_db):
        """已存在的专利不应重新索引"""
        # mock fetchall 返回空（所有专利都已索引）
        mock_db.execute.return_value.fetchall.return_value = []
        count = await engine.backfill()
        assert count == 0

    async def test_backfill_indexes_missing(self, engine, mock_db):
        """未索引的专利应逐个嵌入（backfill 内联嵌入，不调用 index_patent）"""
        mock_db.execute.return_value.fetchall.return_value = [
            {"id": 1, "title": "散热结构", "abstract": "新结构", "claims": "", "description": ""},
            {"id": 2, "title": "无线充电", "abstract": "新方案", "claims": "", "description": ""},
        ]
        count = await engine.backfill()
        assert count == 2
        # backfill 内部直接嵌入+INSERT，每行一次 INSERT
        insert_sqls = [args[0] for args in mock_db.execute.call_args_list
                       if "INSERT INTO patent_vectors" in str(args[0])]
        assert len(insert_sqls) == 2


# ═══════════════════════════════════════════════════════════════
# Test: embed_text (失败路径)
# ═══════════════════════════════════════════════════════════════

class TestEmbedText:

    async def test_embedder_not_configured_raises(self, monkeypatch):
        """embedder 为 None 时应抛 RuntimeError"""
        from app.algorithm.patent_search_engine import PatentSearchEngine, _get_embedder_config
        # Patch _get_embedder_config -> None so embedder stays None
        monkeypatch.setattr("app.algorithm.patent_search_engine._get_embedder_config", lambda: None)
        engine = PatentSearchEngine()
        assert engine.embedder is None
        with pytest.raises(RuntimeError, match="嵌入模型未配置"):
            await engine.embed_text("test")
