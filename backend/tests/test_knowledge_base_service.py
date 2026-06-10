"""
Tests for KnowledgeBaseService — CRUD, validation, and restore.
"""
import pytest
from unittest.mock import patch

SERVICE_PATH = "app.services.knowledge_base_service"


@pytest.fixture(autouse=True)
def _patch_get_db(mock_db):
    with patch(f"{SERVICE_PATH}.get_db", return_value=mock_db):
        yield


def _make_row(**overrides):
    """Build a mock knowledge_base row dict."""
    row = {
        "id": "base-1",
        "name": "Test Base",
        "user_id": 1,
        "group_id": None,
        "dimensions": 768,
        "embedding_model_id": "model-1",
        "status": "completed",
        "error": None,
        "rerank_model_id": None,
        "file_processor_id": None,
        "chunk_size": 1024,
        "chunk_overlap": 200,
        "threshold": 0.5,
        "document_count": 0,
        "search_mode": "hybrid",
        "hybrid_alpha": 0.5,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
    row.update(overrides)
    return row


# ── Basic CRUD ──


class TestCreate:
    def test_create_base_inserts(self, mock_db):
        """create() should issue INSERT with correct columns."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        dto = {
            "name": " My Knowledge Base ",
            "embeddingModelId": "emb-model-1",
            "groupId": "group-1",
            "dimensions": 512,
        }
        mock_db.cursor.add_fetchone_result(_make_row(
            name="My Knowledge Base", embedding_model_id="emb-model-1",
        ))

        result = KnowledgeBaseService.create(user_id=1, dto=dto)

        insert_sql = next(s for s in mock_db.all_sql if s.strip().startswith("INSERT"))
        assert "knowledge_bases" in insert_sql
        assert "name" in insert_sql
        assert "user_id" in insert_sql
        assert "embedding_model_id" in insert_sql
        assert "chunk_size" in insert_sql
        assert "chunk_overlap" in insert_sql
        assert "id" in result
        assert result["name"] == "My Knowledge Base"
        assert result["embeddingModelId"] == "emb-model-1"

    @pytest.mark.parametrize("dto", [
        {"name": "test", "chunkSize": 500, "chunkOverlap": 500},
        {"name": "test", "chunkSize": 200, "chunkOverlap": 500},
    ])
    def test_create_validates_chunk_overlap(self, dto):
        """chunkOverlap >= chunkSize should raise ValueError."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        with pytest.raises(ValueError, match="Validation errors"):
            KnowledgeBaseService.create(user_id=1, dto=dto)


class TestGetById:
    def test_get_by_id_returns_base(self, mock_db):
        """get_by_id() should return a base dict with expected keys."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        mock_db.cursor._fetchone_result = _make_row()

        result = KnowledgeBaseService.get_by_id(user_id=1, base_id="base-1")

        assert result is not None
        assert "id" in result
        assert "name" in result
        assert "chunkSize" in result
        assert "searchMode" in result


class TestList:
    def test_list_bases_returns_paginated(self, mock_db):
        """list() should return paginated results."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        mock_db.cursor._fetchall_result = [
            _make_row(id="base-1", name="First", item_count=3),
            _make_row(id="base-2", name="Second", item_count=0),
        ]
        mock_db.cursor.add_fetchone_result({0: 2})

        result = KnowledgeBaseService.list(user_id=1, page=1, limit=20)

        assert len(result["items"]) == 2
        assert result["total"] == 2
        assert result["page"] == 1
        assert result["items"][0]["itemCount"] == 3
        assert result["items"][1]["name"] == "Second"


class TestDelete:
    def test_delete_base_removes(self, mock_db):
        """delete() should issue DELETE statements."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        mock_db.cursor.add_fetchone_result(_make_row(id="base-1"))

        result = KnowledgeBaseService.delete(user_id=1, base_id="base-1")

        assert result is True
        delete_sqls = [s for s in mock_db.all_sql if "DELETE" in s.upper()]
        assert len(delete_sqls) >= 2
        assert any("knowledge_items" in s for s in delete_sqls)
        assert any("knowledge_bases" in s for s in delete_sqls)


# ── Restore ──


class TestRestore:
    def test_restore_creates_new_base(self, mock_db):
        """restore() should create a new base using source config."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        source_row = _make_row(
            id="source-1", name="Source Base", chunk_size=2048,
            embedding_model_id="old-emb", dimensions=512,
        )
        mock_db.cursor.add_fetchone_result(source_row)
        mock_db.cursor.add_fetchone_result(_make_row(id="new-1", name="Restored"))

        result = KnowledgeBaseService.restore(
            user_id=1,
            source_base_id="source-1",
            new_base_id="new-1",
            dto={"name": "Restored Knowledge Base"},
        )

        insert_sql = next(s for s in mock_db.all_sql if s.strip().startswith("INSERT"))
        assert result is not None
        assert result["id"] == "new-1"
        assert result["name"] == "Restored"
        assert "knowledge_bases" in insert_sql


# ── Update ──


class TestUpdate:
    def test_update_base_updates_fields(self, mock_db):
        """update() should issue UPDATE with dynamic SET clause."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        existing = _make_row(
            name="Old Name", chunk_size=1024, chunk_overlap=200,
            search_mode="hybrid", hybrid_alpha=0.5,
        )
        updated = _make_row(
            name="New Name", chunk_size=2048, chunk_overlap=200,
            search_mode="hybrid", hybrid_alpha=0.5,
        )
        mock_db.cursor.add_fetchone_result(existing)
        mock_db.cursor.add_fetchone_result(updated)

        result = KnowledgeBaseService.update(
            user_id=1,
            base_id="base-1",
            dto={"name": "New Name", "chunkSize": 2048},
        )

        assert result is not None
        update_sql = next(s for s in mock_db.all_sql if s.strip().startswith("UPDATE"))
        assert "knowledge_bases" in update_sql
        assert "name=?" in update_sql
        assert "chunk_size=?" in update_sql

    def test_update_base_not_found(self, mock_db):
        """update() returns None when base doesn't exist."""
        from app.services.knowledge_base_service import KnowledgeBaseService

        mock_db.cursor._fetchone_result = None

        result = KnowledgeBaseService.update(
            user_id=1, base_id="nonexistent", dto={"name": "New"},
        )
        assert result is None
