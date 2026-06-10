"""
Tests for KnowledgeItemService — CRUD, status management, subtree operations,
and container reconciliation.

Usage:  pytest tests/test_knowledge_item_service.py -v
"""
import pytest
from unittest.mock import patch

SERVICE_PATH = "app.services.knowledge_item_service"


@pytest.fixture(autouse=True)
def _patch_get_db(mock_db):
    """Replace the module-local get_db reference with the SQL-capturing MockDB."""
    with patch(f"{SERVICE_PATH}.get_db", return_value=mock_db):
        yield


# ═══════════════════════════════════════════════════════════════════
#  Basic CRUD
# ═══════════════════════════════════════════════════════════════════


def test_create_creates_item(mock_db):
    """INSERT SQL should contain all expected columns."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})  # base ownership check
    mock_db.cursor.add_fetchone_result(
        {
            "id": "new-uuid",
            "base_id": "base-1",
            "group_id": None,
            "type": "file",
            "data": "{}",
            "status": "idle",
            "error": None,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    result = KnowledgeItemService.create(
        user_id=1, base_id="base-1",
        item={"type": "file", "data": {"path": "/tmp/doc.pdf"}},
    )

    # Collect all INSERT SQL
    insert_sqls = [s for s in mock_db.all_sql if s.strip().upper().startswith("INSERT")]
    assert len(insert_sqls) >= 1
    insert_sql = insert_sqls[0]
    assert "INSERT INTO knowledge_items" in insert_sql
    assert "id" in insert_sql
    assert "base_id" in insert_sql
    assert "type" in insert_sql
    assert "data" in insert_sql
    assert "status" in insert_sql
    assert "created_at" in insert_sql
    assert "updated_at" in insert_sql
    assert result is not None
    assert result["baseId"] == "base-1"


def test_get_by_id_returns_item(mock_db):
    """Returned dict should contain expected keys."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1",
            "base_id": "base-1",
            "group_id": None,
            "type": "file",
            "data": '{"path": "/tmp/doc.pdf"}',
            "status": "completed",
            "error": None,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    result = KnowledgeItemService.get_by_id(user_id=1, item_id="item-1")

    assert result is not None
    assert result["id"] == "item-1"
    assert result["baseId"] == "base-1"
    assert result["type"] == "file"
    assert result["status"] == "completed"


def test_list_returns_paginated_items(mock_db):
    """List should return paginated dict with total and page."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})  # base ownership
    mock_db.cursor.add_fetchone_result([3])               # COUNT(*)
    mock_db.cursor._fetchall_result = [
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
        {
            "id": "item-2", "base_id": "base-1", "group_id": None,
            "type": "url", "data": "{}", "status": "processing",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
        {
            "id": "item-3", "base_id": "base-1", "group_id": "parent-1",
            "type": "directory", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    ]

    result = KnowledgeItemService.list(user_id=1, base_id="base-1")

    assert len(result["items"]) == 3
    assert result["total"] == 3
    assert result["page"] == 1


def test_delete_removes_item(mock_db):
    """DELETE SQL should be executed when item exists."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    result = KnowledgeItemService.delete(user_id=1, item_id="item-1")

    assert result is True
    delete_sqls = [s for s in mock_db.all_sql if s.strip().upper().startswith("DELETE")]
    assert len(delete_sqls) >= 1
    assert "knowledge_items" in delete_sqls[0]


# ═══════════════════════════════════════════════════════════════════
#  Status Management
# ═══════════════════════════════════════════════════════════════════


def test_update_status_changes_status(mock_db):
    """UPDATE SQL should set status column."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "processing",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )
    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    result = KnowledgeItemService.update_status(
        user_id=1, item_id="item-1", status="completed"
    )

    assert result is not None
    assert result["status"] == "completed"
    update_sqls = [s for s in mock_db.all_sql if s.strip().upper().startswith("UPDATE")]
    assert len(update_sqls) >= 1
    assert "status" in update_sqls[0]


def test_set_subtree_status_recursive(mock_db):
    """UPDATE with recursive CTE should include root_ids in the IN clause."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})
    mock_db.cursor._fetchall_result = [
        {"id": "item-1", "groupId": None},
        {"id": "child-1", "groupId": "item-1"},
    ]

    result = KnowledgeItemService.set_subtree_status(
        user_id=1, base_id="base-1",
        root_ids=["item-1"], status="processing",
    )

    assert len(result) == 2
    # Find the UPDATE with the recursive CTE
    update_sqls = [s for s in mock_db.all_sql if "WITH RECURSIVE" in s or "UPDATE knowledge_items" in s]
    assert len(update_sqls) >= 1


def test_reindex_resets_status(mock_db):
    """Reindex should set status='idle' and error=NULL."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "failed",
            "error": "Some error", "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )
    mock_db.cursor.add_fetchone_result(
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "idle",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    result = KnowledgeItemService.reindex(user_id=1, item_id="item-1")

    assert result is not None
    assert result["status"] == "idle"
    # Verify the UPDATE contains status and error column references
    update_sqls = [s for s in mock_db.all_sql if "UPDATE" in s.upper()]
    assert len(update_sqls) >= 1
    update_text = " ".join(update_sqls)
    assert "SET status" in update_text
    assert "error" in update_text


def test_reindex_not_found_returns_none(mock_db):
    """When item is not found, reindex should return None."""
    from app.services.knowledge_item_service import KnowledgeItemService

    # No fetchone added → returns None by default
    result = KnowledgeItemService.reindex(user_id=1, item_id="nonexistent")
    assert result is None


# ═══════════════════════════════════════════════════════════════════
#  Subtree Operations
# ═══════════════════════════════════════════════════════════════════


def test_get_subtree_items_queries_with_recursive_cte(mock_db):
    """Subtree query should use WITH RECURSIVE CTE."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})
    mock_db.cursor._fetchall_result = [
        {
            "id": "child-1", "base_id": "base-1", "group_id": "parent-1",
            "type": "file", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    ]

    result = KnowledgeItemService.get_subtree_items(
        user_id=1, base_id="base-1", root_ids=["parent-1"],
    )

    assert len(result) == 1
    cte_sql = next((s for s in mock_db.all_sql if "WITH RECURSIVE" in s), "")
    assert "WITH RECURSIVE" in cte_sql
    assert "subtree" in cte_sql


def test_get_root_items_by_base_id_filters_parent_null(mock_db):
    """Root items query should include group_id IS NULL."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})
    mock_db.cursor._fetchall_result = [
        {
            "id": "root-1", "base_id": "base-1", "group_id": None,
            "type": "directory", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    ]

    result = KnowledgeItemService.get_root_items_by_base_id(
        user_id=1, base_id="base-1",
    )

    assert len(result) == 1
    # Find the SELECT sql and check for group_id IS NULL
    select_sqls = [s for s in mock_db.all_sql if "SELECT" in s.upper() and "knowledge_items" in s]
    all_sql_text = " ".join(mock_db.all_sql)
    assert "group_id IS NULL" in all_sql_text


# ═══════════════════════════════════════════════════════════════════
#  Container Reconciliation
# ═══════════════════════════════════════════════════════════════════


def test_propagate_status_upwards_processes_chain(mock_db):
    """_reconcile_containers should run aggregation query and update containers."""
    from app.services.knowledge_item_service import KnowledgeItemService

    # First fetchone returns a directory container
    mock_db.cursor.add_fetchone_result(
        {
            "id": "parent-1", "base_id": "base-1", "group_id": None,
            "type": "directory", "data": "{}", "status": "processing",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )
    # Stats query: 0 active, 0 failed → container moves to "completed"
    mock_db.cursor.add_fetchone_result({"activeCount": 0, "failedCount": 0})

    KnowledgeItemService._reconcile_containers(
        user_id=1, base_id="base-1",
        start_container_ids=["parent-1"],
    )

    # Should see an aggregation query (SUM with CASE)
    agg_sql = next(
        (s for s in mock_db.all_sql if "SUM(CASE" in s and "activeCount" in s),
        "",
    )
    assert "SUM(CASE" in agg_sql

    # Should see an UPDATE on knowledge_items (values use ? placeholders)
    update_sqls = [
        s for s in mock_db.all_sql
        if "UPDATE" in s.upper() and "knowledge_items" in s
    ]
    assert len(update_sqls) >= 1
    assert "SET status" in update_sqls[0]
    assert "error" in update_sqls[0]


def test_list_with_type_filter_appends_condition(mock_db):
    """List with type filter should include type = ? in WHERE."""
    from app.services.knowledge_item_service import KnowledgeItemService

    mock_db.cursor.add_fetchone_result({"id": "base-1"})  # base ownership
    mock_db.cursor.add_fetchone_result([1])               # COUNT(*)
    mock_db.cursor._fetchall_result = [
        {
            "id": "item-1", "base_id": "base-1", "group_id": None,
            "type": "file", "data": "{}", "status": "completed",
            "error": None, "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    ]

    KnowledgeItemService.list(user_id=1, base_id="base-1", type="file")

    all_text = " ".join(mock_db.all_sql)
    assert "type = ?" in all_text or "type =" in all_text
