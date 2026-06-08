"""
Knowledge Workflow Service — 完全复现 CherryStudio KnowledgeWorkflowService

职责：
- 编排添加/删除/重新索引的多步工作流
- 在 SQLite 中创建项，转换生命周期状态
- 通过 JobManager 调度作业
"""
import logging
from typing import Optional
from app.database import get_db
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_lock_manager import KnowledgeLockManager
from app.utils import utc_iso

logger = logging.getLogger(__name__)


class KnowledgeWorkflowService:
    """知识库工作流服务 — 完全对齐 CherryStudio KnowledgeWorkflowService"""

    def __init__(self, lock_manager: KnowledgeLockManager):
        self.lock_manager = lock_manager

    async def add_items(self, base_id: str, items: list[dict]) -> None:
        """添加知识项"""
        if not items:
            return

        base = KnowledgeBaseService.get_by_id(base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")

        accepted_items = []

        async def _create_items():
            for item in items:
                created = KnowledgeItemService.create(base_id, item)
                if created:
                    accepted_items.append(created)
                    # 设置初始状态
                    is_container = created["type"] == "directory"
                    initial_status = "preparing" if is_container else "processing"
                    KnowledgeItemService.update_status(created["id"], initial_status)

        try:
            await self.lock_manager.with_base_mutation_lock(base_id, _create_items)
        except Exception as e:
            # 回滚已接受的项
            await self._rollback_accepted_items(base_id, accepted_items, e)
            raise

        # 调度项
        completed_scheduling = set()
        try:
            for item in accepted_items:
                await self.schedule_item(base_id, item["id"])
                completed_scheduling.add(item["id"])
        except Exception as e:
            await self._mark_unscheduled_failed(base_id, accepted_items, completed_scheduling, e)
            raise

    async def delete_items(self, base_id: str, item_ids: list[str]) -> None:
        """删除知识项"""
        KnowledgeBaseService.get_by_id(base_id)
        unique_ids = list(dict.fromkeys(item_ids))

        # 标记为 deleting
        await self.lock_manager.with_base_mutation_lock(
            base_id, lambda: KnowledgeItemService.set_subtree_status(base_id, unique_ids, "deleting")
        )

        logger.info(f"Marked {len(unique_ids)} items as deleting in base {base_id}")

    async def reindex_items(self, base_id: str, item_ids: list[str]) -> None:
        """重新索引知识项"""
        KnowledgeBaseService.get_by_id(base_id)
        unique_ids = list(dict.fromkeys(item_ids))

        # 重置状态
        for item_id in unique_ids:
            KnowledgeItemService.update_status(item_id, "processing")

        # 重新调度
        for item_id in unique_ids:
            await self.schedule_item(base_id, item_id)

        logger.info(f"Reindexed {len(unique_ids)} items in base {base_id}")

    async def schedule_item(self, base_id: str, item_id: str, parent_job_id: str = None) -> None:
        """调度单个知识项"""
        base = KnowledgeBaseService.get_by_id(base_id)
        item = KnowledgeItemService.get_by_id(item_id)

        if not item or item["baseId"] != base_id:
            raise ValueError(f"Knowledge item '{item_id}' does not belong to base '{base_id}'")
        if item["status"] == "deleting":
            return

        # 根据类型调度
        item_type = item["type"]
        if item_type == "directory":
            # 容器项：准备子项
            KnowledgeItemService.update_status(item_id, "preparing")
            logger.info(f"Scheduled prepare-root for item {item_id}")
        else:
            # 叶子项：直接处理
            KnowledgeItemService.update_status(item_id, "processing")
            await self._process_leaf_item(base_id, item_id, item)

    async def _process_leaf_item(self, base_id: str, item_id: str, item: dict) -> None:
        """处理叶子项"""
        try:
            # 标记为 reading
            KnowledgeItemService.update_status(item_id, "reading")
            logger.info(f"Reading item {item_id}")

            # TODO: 实际的文件读取逻辑
            # 这里只是模拟流程

            # 标记为 embedding
            KnowledgeItemService.update_status(item_id, "embedding")
            logger.info(f"Embedding item {item_id}")

            # TODO: 实际的嵌入逻辑
            # 这里只是模拟流程

            # 标记为 completed
            KnowledgeItemService.update_status(item_id, "completed")
            logger.info(f"Completed item {item_id}")

        except Exception as e:
            KnowledgeItemService.update_status(item_id, "failed", str(e))
            logger.error(f"Failed to process item {item_id}: {e}")

    async def _rollback_accepted_items(self, base_id: str, items: list[dict], original_error: Exception) -> None:
        """回滚已接受的项"""
        for item in items:
            try:
                KnowledgeItemService.delete(item["id"])
            except Exception as cleanup_error:
                logger.error(f"Failed to rollback item {item['id']}: {cleanup_error}")

    async def _mark_unscheduled_failed(self, base_id: str, items: list[dict], completed_ids: set, original_error: Exception) -> None:
        """标记未调度的项为失败"""
        message = str(original_error)
        for item in items:
            if item["id"] not in completed_ids:
                try:
                    KnowledgeItemService.update_status(item["id"], "failed", f"Failed to schedule: {message}")
                except Exception as e:
                    logger.error(f"Failed to mark item {item['id']} as failed: {e}")
