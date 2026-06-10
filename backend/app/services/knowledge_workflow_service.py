"""
Knowledge Workflow Service — 完全复现 CherryStudio KnowledgeWorkflowService

职责：
- 编排添加/删除/重新索引的多步工作流
- 在 SQLite 中创建项，转换生命周期状态
- 通过 JobManager 调度作业
- 目录导入：处理上传的文件列表
"""
import logging

from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_job_manager import (
    KnowledgeJobManager,
    JOB_TYPE_PREPARE_ROOT,
    JOB_TYPE_INDEX_DOCUMENTS,
    JOB_TYPE_DELETE_SUBTREE,
    JOB_TYPE_REINDEX_SUBTREE,
    knowledge_queue_name,
    knowledge_idempotency_key,
)
from app.services.knowledge_lock_manager import KnowledgeLockManager

logger = logging.getLogger(__name__)


class KnowledgeWorkflowService:
    """知识库工作流服务 — 完全对齐 CherryStudio KnowledgeWorkflowService"""

    def __init__(self, lock_manager: KnowledgeLockManager, job_manager: KnowledgeJobManager):
        self.lock_manager = lock_manager
        self.job_manager = job_manager

    # ─── Idempotency key helpers ──────────────────────────────────────

    def _idempotency_key(self, prefix: str, *parts: str) -> str:
        """Generate an idempotency key for a knowledge job."""
        return knowledge_idempotency_key(prefix, *parts)

    # ─── Public API ───────────────────────────────────────────────────

    async def add_items(self, user_id: int, base_id: str, items: list[dict]) -> None:
        """添加知识项"""
        if not items:
            return

        base = KnowledgeBaseService.get_by_id(user_id, base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")

        accepted_items = []

        async def _create_items():
            for item in items:
                created = KnowledgeItemService.create(user_id, base_id, item)
                if created:
                    accepted_items.append(created)
                    # 设置初始状态
                    is_container = created["type"] == "directory"
                    initial_status = "preparing" if is_container else "processing"
                    KnowledgeItemService.update_status(user_id, created["id"], initial_status)

        try:
            await self.lock_manager.with_base_mutation_lock(base_id, _create_items)
        except Exception as e:
            # 回滚已接受的项
            for item in accepted_items:
                try:
                    KnowledgeItemService.delete(user_id, item["id"])
                except Exception as cleanup_error:
                    logger.error(f"Failed to rollback item {item['id']}: {cleanup_error}")
            raise

        # 通过 JobManager 调度作业
        for item in accepted_items:
            if item["type"] == "directory":
                await self.job_manager.enqueue(
                    JOB_TYPE_PREPARE_ROOT,
                    {"baseId": base_id, "itemId": item["id"]},
                    queue=knowledge_queue_name(base_id),
                    idempotency_key=self._idempotency_key("add", base_id, item["id"]),
                )
            else:
                await self.job_manager.enqueue(
                    JOB_TYPE_INDEX_DOCUMENTS,
                    {"baseId": base_id, "itemId": item["id"]},
                    queue=knowledge_queue_name(base_id),
                    idempotency_key=self._idempotency_key("add", base_id, item["id"]),
                )

    async def delete_items(self, user_id: int, base_id: str, item_ids: list[str]) -> None:
        """删除知识项"""
        KnowledgeBaseService.get_by_id(user_id, base_id)
        unique_ids = list(dict.fromkeys(item_ids))

        # 标记为 deleting
        await self.lock_manager.with_base_mutation_lock(
            base_id, lambda: KnowledgeItemService.set_subtree_status(user_id, base_id, unique_ids, "deleting")
        )

        # 入队删除作业
        await self.job_manager.enqueue(
            JOB_TYPE_DELETE_SUBTREE,
            {"baseId": base_id, "rootItemIds": unique_ids},
            queue=knowledge_queue_name(base_id),
            idempotency_key=self._idempotency_key("delete", base_id, *unique_ids),
        )

        logger.info(f"Marked {len(unique_ids)} items as deleting in base {base_id}")

    async def reindex_items(self, user_id: int, base_id: str, item_ids: list[str]) -> None:
        """重新索引知识项"""
        KnowledgeBaseService.get_by_id(user_id, base_id)
        unique_ids = list(dict.fromkeys(item_ids))

        # 入队重新索引作业
        await self.job_manager.enqueue(
            JOB_TYPE_REINDEX_SUBTREE,
            {"baseId": base_id, "rootItemIds": unique_ids},
            queue=knowledge_queue_name(base_id),
            idempotency_key=self._idempotency_key("reindex", base_id, *unique_ids),
        )

        logger.info(f"Reindex enqueued for {len(unique_ids)} items in base {base_id}")
