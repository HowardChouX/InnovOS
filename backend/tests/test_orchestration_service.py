"""
TDD #3: KnowledgeOrchestrationService — 实现 TODO list_item_chunks / delete_item_chunk
Usage:  pytest tests/test_orchestration_service.py -v
"""
import pytest
from unittest.mock import patch, AsyncMock

SERVICE_PATH = "app.services.knowledge_orchestration_service"


@pytest.fixture(autouse=True)
def _patch_get_db(mock_db):
    with patch(f"{SERVICE_PATH}.get_db", return_value=mock_db):
        yield


@pytest.fixture
def orch():
    from app.services.knowledge_orchestration_service import KnowledgeOrchestrationService
    return KnowledgeOrchestrationService()


@pytest.mark.asyncio
async def test_list_item_chunks_returns_chunks_for_completed_item(orch, mock_db):
    """list_item_chunks should query knowledge_vectors for item's doc_id."""
    item = {
        "id": "item-1", "base_id": "base-1",
        "type": "file", "status": "completed",
        "data": '{"fileEntryId": 42}',
    }
    with patch(f"{SERVICE_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch.object(orch, "_assert_base_can_run_runtime_operation", AsyncMock()):
            mock_db.cursor.add_fetchone_result({"id": "base-1", "status": "completed"})
            mock_db.cursor._fetchall_result = [
                {"id": 1, "chunk_index": 0, "text": "chunk1"},
                {"id": 2, "chunk_index": 1, "text": "chunk2"},
            ]

            result = await orch.list_item_chunks(user_id=1, base_id="base-1", item_id="item-1")

    assert len(result) == 2
    # Verify SQL queried knowledge_vectors with user_id + doc_id
    vec_sql = next((s for s in mock_db.all_sql if "knowledge_vectors" in s), "")
    assert "knowledge_vectors" in vec_sql
    assert "user_id" in vec_sql
    assert "doc_id" in vec_sql


@pytest.mark.asyncio
async def test_list_item_chunks_no_fileEntryId(orch, mock_db):
    """When item has no fileEntryId, return empty list."""
    item = {"id": "item-1", "base_id": "base-1", "type": "note", "status": "completed", "data": "{}"}
    with patch(f"{SERVICE_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch.object(orch, "_assert_base_can_run_runtime_operation", AsyncMock()):
            result = await orch.list_item_chunks(user_id=1, base_id="base-1", item_id="item-1")
    assert result == []


@pytest.mark.asyncio
async def test_delete_item_chunk_removes_vector(orch, mock_db):
    """delete_item_chunk should DELETE from knowledge_vectors."""
    item = {
        "id": "item-1", "base_id": "base-1",
        "type": "file", "status": "completed",
        "data": '{"fileEntryId": 42}',
    }
    with patch(f"{SERVICE_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch.object(orch, "_assert_base_can_run_runtime_operation", AsyncMock()):
            await orch.delete_item_chunk(user_id=1, base_id="base-1", item_id="item-1", chunk_id="99")

    vec_sql = next((s for s in mock_db.all_sql if "knowledge_vectors" in s), "")
    assert "DELETE" in vec_sql.upper()
    assert "user_id" in vec_sql
    assert "id" in vec_sql
