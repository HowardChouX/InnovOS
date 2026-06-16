"""
PatentSearchEngine TDD 测试

覆盖：index_patent, search, delete_patent, backfill, embed_text
策略：mock Embedder（避免 API 调用），mock get_db（避免 PostgreSQL）
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── PatentSearchEngine 初始化（mock embedder 防止 API 调用） ──


@pytest.fixture(autouse=True)
def mock_embedder(monkeypatch):
    """替换 PatentSearchEngine.embed_text 为固定向量（1024-dim）"""
    fake_vec = [0.1] * 1024
    monkeypatch.setattr(
        "app.algorithm.patent_search_engine.PatentSearchEngine.embed_text",
        AsyncMock(return_value=fake_vec),
    )


@pytest.fixture
def engine():
    from app.algorithm.patent_search_engine import PatentSearchEngine
    return PatentSearchEngine()


@pytest.fixture
def mock_db(monkeypatch):
    """Mock get_db 返回可控的 MagicMock"""
    conn = MagicMock()
    monkeypatch.setattr("app.database.get_db", lambda: conn)
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

    async def test_search_pg_calls_operator(self, engine, monkeypatch):
        """PG 环境下应使用 <=> 算子"""
        # Mock is_postgres -> True
        monkeypatch.setattr("app.database.is_postgres", lambda: True)

        conn = MagicMock()
        monkeypatch.setattr("app.database.get_db", lambda: conn)

        fake_rows = [
            {"id": 1, "title": "散热结构", "abstract": "摘要", "patent_number": "CN123", "applicant": "华为",
             "relevance": 0.95}
        ]
        conn.execute.return_value.fetchall.return_value = fake_rows

        results = await engine.search("散热")
        assert len(results) == 1
        assert results[0]["relevance"] == 0.95

        # 验证使用了 <=> 算子
        call_sql = conn.execute.call_args[0][0]
        assert "<->" in call_sql or "<=>" in call_sql

    async def test_search_sqlite_fallback(self, engine, monkeypatch):
        """SQLite 环境应使用全表扫描 + numpy"""
        monkeypatch.setattr("app.database.is_postgres", lambda: False)

        conn = MagicMock()
        monkeypatch.setattr("app.database.get_db", lambda: conn)

        # 返回 fake rows 包含 embedding JSON
        fake_vec_str = json.dumps([0.1] * 1024)
        fake_rows = [
            {"patent_id": 1, "embedding": fake_vec_str, "title": "散热结构", "abstract": "摘要",
             "patent_number": "CN123", "applicant": "华为"}
        ]
        conn.execute.return_value.fetchall.return_value = fake_rows

        results = await engine.search("散热", top_k=3)
        assert len(results) == 1
        # 余弦相似度应为 1.0（向量完全一样）
        assert results[0]["relevance"] == 1.0


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
        """未索引的专利应逐个嵌入"""
        mock_db.execute.return_value.fetchall.return_value = [
            {"id": 1, "title": "散热结构", "abstract": "新结构"},
            {"id": 2, "title": "无线充电", "abstract": "新方案"},
        ]
        with patch.object(engine, 'index_patent', AsyncMock(return_value=True)):
            count = await engine.backfill()
            assert count == 2
            assert engine.index_patent.call_count == 2


# ═══════════════════════════════════════════════════════════════
# Test: embed_text (失败路径)
# ═══════════════════════════════════════════════════════════════

class TestEmbedText:

    async def test_embedder_not_configured_raises(self, monkeypatch):
        """embedder 为 None 时应抛 RuntimeError"""
        monkeypatch.setattr(
            "app.algorithm.patent_search_engine.PatentSearchEngine",
            "embedder",
            None,
        )
        # 重新创建 engine 用没有 embedder 的配置
        from app.algorithm.patent_search_engine import PatentSearchEngine, _get_embedder_config
        # Patch _get_embedder_config -> None
        monkeypatch.setattr("app.algorithm.patent_search_engine._get_embedder_config", lambda: None)
        engine = PatentSearchEngine()
        assert engine.embedder is None
        with pytest.raises(RuntimeError, match="嵌入模型未配置"):
            await engine.embed_text("test")
