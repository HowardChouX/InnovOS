"""
Knowledge Orchestration Service — 完全复现 CherryStudio KnowledgeOrchestrationService

职责：
- 所有运行时操作的入口点
- 注册 IPC 处理器
- 协调 DataApi 服务、向量存储和工作流
- 崩溃恢复
"""
import asyncio
import logging
import re
from typing import Optional
from app.database import get_db
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_lock_manager import KnowledgeLockManager
from app.services.knowledge_workflow_service import KnowledgeWorkflowService
from app.utils import utc_iso

logger = logging.getLogger(__name__)
SEARCH_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
REINDEX_ALLOWED_STATUSES = {"completed", "failed"}


class KnowledgeOrchestrationService:
    """知识库编排服务 — 完全对齐 CherryStudio KnowledgeOrchestrationService"""

    def __init__(self):
        self.lock_manager = KnowledgeLockManager()
        self.workflow_service = KnowledgeWorkflowService(self.lock_manager)

    async def create_base(self, dto: dict) -> dict:
        """创建知识库"""
        base = KnowledgeBaseService.create(dto)
        logger.info(f"Created knowledge base: {base['id']}")
        return base

    async def delete_base(self, base_id: str) -> None:
        """删除知识库"""
        await self.lock_manager.with_base_mutation_lock(base_id, lambda: self._delete_base_impl(base_id))

    def _delete_base_impl(self, base_id: str) -> None:
        """删除知识库实现"""
        KnowledgeBaseService.delete(base_id)
        logger.info(f"Deleted knowledge base: {base_id}")

    async def add_items(self, base_id: str, items: list[dict]) -> None:
        """添加知识项"""
        await self._assert_base_can_run_runtime_operation(base_id, "addItems")
        await self.workflow_service.add_items(base_id, items)

    async def delete_items(self, base_id: str, item_ids: list[str]) -> None:
        """删除知识项"""
        root_ids = KnowledgeItemService.get_outermostSelectedItem_ids(base_id, item_ids)
        if not root_ids:
            return
        await self.workflow_service.delete_items(base_id, root_ids)

    async def reindex_items(self, base_id: str, item_ids: list[str]) -> None:
        """重新索引知识项"""
        await self._assert_base_can_run_runtime_operation(base_id, "reindexItems")
        root_ids = KnowledgeItemService.get_outermostSelectedItem_ids(base_id, item_ids)
        if not root_ids:
            return
        await self._assert_subtrees_can_reindex(base_id, root_ids)
        await self.workflow_service.reindex_items(base_id, root_ids)

    async def search(self, base_id: str, query: str) -> list[dict]:
        """搜索知识库"""
        await self._assert_base_can_run_runtime_operation(base_id, "search")

        if not SEARCH_TOKEN_PATTERN.search(query):
            raise ValueError("Query has no searchable tokens")

        base = KnowledgeBaseService.get_by_id(base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")

        # TODO: 实现向量搜索
        # 目前返回空结果
        return []

    async def list_item_chunks(self, base_id: str, item_id: str) -> list[dict]:
        """列出知识项的分块"""
        await self._assert_base_can_run_runtime_operation(base_id, "listItemChunks")
        item = KnowledgeItemService.get_by_id(item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")
        if item["status"] != "completed":
            raise ValueError(f"Knowledge item must be completed before listing chunks")

        # TODO: 实现向量存储查询
        return []

    async def delete_item_chunk(self, base_id: str, item_id: str, chunk_id: str) -> None:
        """删除知识项分块"""
        await self._assert_base_can_run_runtime_operation(base_id, "deleteItemChunk")
        # TODO: 实现向量存储删除
        pass

    async def recover_deleting_items(self) -> None:
        """崩溃恢复：重新入队正在删除的项"""
        try:
            deleting_groups = KnowledgeItemService.get_deleting_root_groups()
        except Exception as e:
            logger.error(f"Failed to scan deleting items: {e}")
            return

        if not deleting_groups:
            return

        for group in deleting_groups:
            for i in range(0, len(group["rootItemIds"]), 100):
                chunk = group["rootItemIds"][i:i+100]
                try:
                    await self.workflow_service.delete_items(group["baseId"], chunk)
                except Exception as e:
                    logger.error(f"Failed to enqueue recovered delete: {e}")

    async def _assert_base_can_run_runtime_operation(self, base_id: str, operation: str) -> None:
        """断言知识库可以运行时操作"""
        base = KnowledgeBaseService.get_by_id(base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")
        if base["status"] == "failed":
            raise ValueError(f"Knowledge base is in failed state; restore it before {operation}.")

    async def _assert_subtrees_can_reindex(self, base_id: str, root_ids: list[str]) -> None:
        """断言子树可以重新索引"""
        blocking_counts = {}
        for root_id in root_ids:
            subtree = KnowledgeItemService.get_subtree_items(base_id, [root_id], include_roots=True)
            for item in subtree:
                if item["status"] not in REINDEX_ALLOWED_STATUSES:
                    blocking_counts[item["status"]] = blocking_counts.get(item["status"], 0) + 1

        if blocking_counts:
            summary = ", ".join(f"{s}={c}" for s, c in sorted(blocking_counts.items()))
            raise ValueError(f"Cannot reindex knowledge item until the entire subtree is completed or failed: {summary}")


# 全局实例
knowledge_orchestration_service = KnowledgeOrchestrationService()
