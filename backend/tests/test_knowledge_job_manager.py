"""
Tests for KnowledgeJobManager — 轻量级异步作业系统
"""
import pytest
from unittest.mock import patch, MagicMock


# ── 模块级常量 ──
# JOB_TYPE_* constants defined inside test functions (imported locally per pattern)


@pytest.fixture(autouse=True)
def _patch_get_db(mock_db):
    """
    Override the auto_mock_db fixture for this module.
    Patches the local 'get_db' reference in knowledge_job_manager
    with the controllable MockDB (CaptureCursor) from conftest.
    """
    with patch("app.services.knowledge_job_manager.get_db", return_value=mock_db):
        yield


# ═══════════════════════════════════════════════════════════════
#  Core Operations  (4 tests)
# ═══════════════════════════════════════════════════════════════

class TestCoreOperations:
    """核心操作 — enqueue / register_handler / cancel_job"""

    @pytest.mark.asyncio
    async def test_enqueue_creates_job_record(self, mock_db):
        """入队应在 knowledge_jobs 表中执行 INSERT"""
        from app.services.knowledge_job_manager import KnowledgeJobManager
        mgr = KnowledgeJobManager()

        handler = MagicMock()
        handler.max_attempts = 3
        handler.timeout_ms = 600000
        mgr.register_handler("knowledge.test-type", handler)

        with patch.object(mgr, "_trigger_job") as mock_trigger:
            job_id = await mgr.enqueue(
                "knowledge.test-type", {"key": "value"}, queue="test-queue",
            )

        # Exactly one INSERT into knowledge_jobs
        inserts = [s for s in mock_db.all_sql if "INSERT INTO knowledge_jobs" in s]
        assert len(inserts) == 1
        assert "knowledge_jobs" in inserts[0]

        # _trigger_job was called with the returned job_id
        mock_trigger.assert_called_once_with(job_id)

    @pytest.mark.asyncio
    async def test_enqueue_returns_job_id(self, mock_db):
        """入队返回的 job_id 应包含类型前缀 + uuid 片段"""
        from app.services.knowledge_job_manager import KnowledgeJobManager
        mgr = KnowledgeJobManager()

        handler = MagicMock()
        handler.max_attempts = 3
        handler.timeout_ms = 600000
        mgr.register_handler("knowledge.test-type", handler)

        with patch.object(mgr, "_trigger_job"):
            job_id = await mgr.enqueue(
                "knowledge.test-type", {"key": "value"},
            )

        assert job_id.startswith("kj-test-type-")
        assert len(job_id) > len("kj-test-type-")

    def test_register_handler_stores_handler(self):
        """register_handler 应将 handler 存入 _handlers 字典"""
        from app.services.knowledge_job_manager import KnowledgeJobManager
        mgr = KnowledgeJobManager()
        handler = MagicMock()
        mgr.register_handler("knowledge.some-type", handler)
        assert mgr._handlers["knowledge.some-type"] is handler

    @pytest.mark.asyncio
    async def test_cancel_job_sets_signal(self, mock_db):
        """取消作业应设置对应 asyncio.Event 并更新 DB 状态"""
        from app.services.knowledge_job_manager import (
            KnowledgeJobManager,
            JobHandle,
        )
        mgr = KnowledgeJobManager()
        handle = JobHandle(job_id="test-job-1", job_type="knowledge.test")
        mgr._handles["test-job-1"] = handle

        mgr.cancel_job("test-job-1", reason="unit-test")

        # asyncio.Event is set
        assert handle.cancel_event.is_set()

        # DB UPDATE was executed (via _update_status)
        updates = [s for s in mock_db.all_sql if "UPDATE" in s.upper()]
        assert len(updates) >= 1


# ═══════════════════════════════════════════════════════════════
#  Batch Operations  (2 tests)
# ═══════════════════════════════════════════════════════════════

class TestBatchOperations:
    """批量操作 — cancel_jobs_for_base / idempotency"""

    def test_cancel_jobs_for_base_cancels_multiple(self, mock_db):
        """cancel_jobs_for_base 应取消知识库下所有活跃作业"""
        from app.services.knowledge_job_manager import (
            KnowledgeJobManager,
            JobHandle,
        )
        mgr = KnowledgeJobManager()

        # Seed 3 active handles
        handles = {}
        for i in range(3):
            jid = f"job-{i}"
            handle = JobHandle(job_id=jid, job_type="knowledge.test")
            mgr._handles[jid] = handle
            handles[jid] = handle

        # DB returns 3 pending/running jobs
        mock_db.cursor._fetchall_result = [
            {"id": "job-0"},
            {"id": "job-1"},
            {"id": "job-2"},
        ]

        mgr.cancel_jobs_for_base("base-1", reason="test")

        # All handles cancelled
        for h in handles.values():
            assert h.cancel_event.is_set(), f"Handle {h.job_id} was not cancelled"

    @pytest.mark.asyncio
    async def test_enqueue_with_idempotency_key_skips_duplicate(self, mock_db):
        """相同幂等键的入队应返回已有 job_id 且不重复 INSERT"""
        from app.services.knowledge_job_manager import KnowledgeJobManager
        mgr = KnowledgeJobManager()

        handler = MagicMock()
        handler.max_attempts = 3
        handler.timeout_ms = 600000
        mgr.register_handler("knowledge.test-type", handler)

        # _find_by_idempotency_key will find an existing job
        mock_db.cursor.add_fetchone_result({"id": "existing-job-id"})

        with patch.object(mgr, "_trigger_job"):
            job_id = await mgr.enqueue(
                "knowledge.test-type",
                {"key": "value"},
                idempotency_key="test:key:123",
            )

        assert job_id == "existing-job-id"

        # No INSERT was executed
        inserts = [s for s in mock_db.all_sql if "INSERT INTO knowledge_jobs" in s]
        assert len(inserts) == 0


# ═══════════════════════════════════════════════════════════════
#  Recovery  (2 tests)
# ═══════════════════════════════════════════════════════════════

class TestRecovery:
    """崩溃恢复机制 — recover_stalled_jobs / recover_deleting_items"""

    def test_recover_stalled_jobs_restarts_running(self, mock_db):
        """recover_stalled_jobs 应将 running 作业重置为 pending 并重新触发"""
        from app.services.knowledge_job_manager import KnowledgeJobManager
        mgr = KnowledgeJobManager()

        # 2 stuck jobs in 'running' status
        mock_db.cursor._fetchall_result = [
            {"id": "job-1", "job_type": "knowledge.test",
             "input_data": "{}", "queue": "q1"},
            {"id": "job-2", "job_type": "knowledge.test",
             "input_data": "{}", "queue": "q2"},
        ]

        with patch.object(mgr, "_trigger_job") as mock_trigger:
            mgr.recover_stalled_jobs()

        # Both re-triggered
        assert mock_trigger.call_count == 2
        mock_trigger.assert_any_call("job-1")
        mock_trigger.assert_any_call("job-2")

        # Two UPDATEs issued (status -> pending via _update_status)
        updates = [s for s in mock_db.all_sql if "UPDATE" in s.upper()]
        assert len(updates) == 2

    @pytest.mark.asyncio
    async def test_recover_deleting_items_enqueues_delete_subtree(self, mock_db):
        """recover_deleting_items 应对每个删除中的组入队 DELETE_SUBTREE 作业"""
        from app.services.knowledge_job_manager import (
            KnowledgeJobManager,
            JOB_TYPE_DELETE_SUBTREE,
        )
        mgr = KnowledgeJobManager()

        handler = MagicMock()
        handler.max_attempts = 3
        handler.timeout_ms = 600000
        mgr.register_handler(JOB_TYPE_DELETE_SUBTREE, handler)

        # Two deleting groups
        deleting_groups = [
            {"baseId": "base-1", "rootItemIds": ["item-1", "item-2"]},
            {"baseId": "base-2", "rootItemIds": ["item-3"]},
        ]

        # get_deleting_root_groups is a static method imported inside the
        # function body, so we patch it directly on the source module.
        with patch(
            "app.services.knowledge_item_service.KnowledgeItemService.get_deleting_root_groups",
            return_value=deleting_groups,
        ):
            with patch.object(mgr, "_trigger_job"):
                await mgr.recover_deleting_items(
                    user_id=1, workflow_service=None,
                )

        # One INSERT per group
        inserts = [s for s in mock_db.all_sql if "INSERT INTO knowledge_jobs" in s]
        assert len(inserts) == 2
