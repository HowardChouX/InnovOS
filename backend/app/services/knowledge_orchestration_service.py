"""
Knowledge Orchestration Service — 完全复现 CherryStudio KnowledgeOrchestrationService

职责：
- 所有运行时操作的入口点
- 注册 IPC 处理器
- 协调 DataApi 服务、向量存储和工作流
- 崩溃恢复
"""
import json
import logging
import re

from app.database import get_db
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_job_manager import (
    KnowledgeJobManager,
    JOB_TYPE_PREPARE_ROOT,
    JOB_TYPE_INDEX_DOCUMENTS,
    JOB_TYPE_DELETE_SUBTREE,
    JOB_TYPE_REINDEX_SUBTREE,
    JOB_TYPE_CHECK_PROCESSING_RESULT,
)
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
        self.job_manager = KnowledgeJobManager()
        self.workflow_service = KnowledgeWorkflowService(self.lock_manager, self.job_manager)

        # ─── 注册作业处理器 ──────────────────────────────────────
        from app.services.knowledge_jobs.prepare_root import PrepareRootHandler
        from app.services.knowledge_jobs.index_documents import IndexDocumentsHandler
        from app.services.knowledge_jobs.delete_subtree import DeleteSubtreeHandler
        from app.services.knowledge_jobs.reindex_subtree import ReindexSubtreeHandler

        prepare_root = PrepareRootHandler(self.job_manager)
        index_docs = IndexDocumentsHandler(self.job_manager, self.lock_manager)
        delete_subtree = DeleteSubtreeHandler(self.job_manager)
        reindex_subtree = ReindexSubtreeHandler(self.job_manager)

        self.job_manager.register_handler(JOB_TYPE_PREPARE_ROOT, prepare_root)
        self.job_manager.register_handler(JOB_TYPE_INDEX_DOCUMENTS, index_docs)
        self.job_manager.register_handler(JOB_TYPE_DELETE_SUBTREE, delete_subtree)
        self.job_manager.register_handler(JOB_TYPE_REINDEX_SUBTREE, reindex_subtree)

        from app.services.knowledge_jobs.check_processing_result import CheckProcessingResultHandler

        check_processing = CheckProcessingResultHandler(self.job_manager, self.lock_manager)
        self.job_manager.register_handler(JOB_TYPE_CHECK_PROCESSING_RESULT, check_processing)

    # ─── Startup ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """启动恢复：恢复卡住的任务和正在删除的项"""
        self.job_manager.recover_stalled_jobs()

        # 对所有有知识库的用户恢复正在删除的项
        db = get_db()
        try:
            user_rows = db.execute(
                "SELECT DISTINCT user_id FROM knowledge_bases"
            ).fetchall()
            for row in user_rows:
                uid = row["user_id"]
                await self.job_manager.recover_deleting_items(uid, self.workflow_service)
        finally:
            db.close()

    # ─── Public API ───────────────────────────────────────────────────

    async def create_base(self, user_id: int, dto: dict) -> dict:
        """创建知识库"""
        base = KnowledgeBaseService.create(user_id, dto)
        logger.info(f"Created knowledge base: {base['id']}")
        return base

    async def delete_base(self, user_id: int, base_id: str) -> None:
        """删除知识库"""
        # 取消所有活跃作业
        self.job_manager.cancel_jobs_for_base(base_id, reason="base-deleted")

        await self.lock_manager.with_base_mutation_lock(
            base_id, lambda: KnowledgeBaseService.delete(user_id, base_id)
        )
        logger.info(f"Deleted knowledge base: {base_id}")

    async def add_items(self, user_id: int, base_id: str, items: list[dict]) -> None:
        """添加知识项"""
        await self._assert_base_can_run_runtime_operation(user_id, base_id, "addItems")
        await self.workflow_service.add_items(user_id, base_id, items)

    async def delete_items(self, user_id: int, base_id: str, item_ids: list[str]) -> None:
        """删除知识项"""
        root_ids = KnowledgeItemService.get_outermostSelectedItem_ids(user_id, base_id, item_ids)
        if not root_ids:
            return
        await self.workflow_service.delete_items(user_id, base_id, root_ids)

    async def reindex_items(self, user_id: int, base_id: str, item_ids: list[str]) -> None:
        """重新索引知识项"""
        await self._assert_base_can_run_runtime_operation(user_id, base_id, "reindexItems")
        root_ids = KnowledgeItemService.get_outermostSelectedItem_ids(user_id, base_id, item_ids)
        if not root_ids:
            return
        await self._assert_subtrees_can_reindex(user_id, base_id, root_ids)
        await self.workflow_service.reindex_items(user_id, base_id, root_ids)

    async def search(self, user_id: int, base_id: str, query: str, top_k: int = 10) -> list[dict]:
        """搜索知识库（完整实现：嵌入 → 向量检索 → 重排）"""
        await self._assert_base_can_run_runtime_operation(user_id, base_id, "search")

        if not SEARCH_TOKEN_PATTERN.search(query):
            raise ValueError("Query has no searchable tokens")

        base = KnowledgeBaseService.get_by_id(user_id, base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")

        from app.algorithm.knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline(user_id=user_id, base_id=base_id)
        results = await pipeline.search(
            query,
            top_k=top_k,
            use_rerank=bool(base.get("rerankModelId")),
        )
        return results

    async def list_item_chunks(self, user_id: int, base_id: str, item_id: str) -> list[dict]:
        """列出知识项的分块（从 knowledge_vectors 表查询）"""
        await self._assert_base_can_run_runtime_operation(user_id, base_id, "listItemChunks")
        item = KnowledgeItemService.get_by_id(user_id, item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")
        if item["status"] != "completed":
            raise ValueError(f"Knowledge item must be completed before listing chunks")

        # 从 item.data 中提取 fileEntryId（对应 knowledge_docs.id）
        data = json.loads(item["data"]) if isinstance(item["data"], str) else item.get("data", {})
        doc_id = data.get("fileEntryId")
        if not doc_id:
            return []

        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, chunk_index, text
                   FROM knowledge_vectors
                   WHERE user_id=? AND doc_id=?
                   ORDER BY chunk_index""",
                (user_id, doc_id),
            ).fetchall()
            return [{"id": r["id"], "chunkIndex": r["chunk_index"], "text": r["text"]} for r in rows]
        finally:
            db.close()

    async def delete_item_chunk(self, user_id: int, base_id: str, item_id: str, chunk_id: str) -> None:
        """删除知识项分块"""
        await self._assert_base_can_run_runtime_operation(user_id, base_id, "deleteItemChunk")
        item = KnowledgeItemService.get_by_id(user_id, item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")

        data = json.loads(item["data"]) if isinstance(item["data"], str) else item.get("data", {})
        doc_id = data.get("fileEntryId")
        if not doc_id:
            return

        db = get_db()
        try:
            db.execute(
                """DELETE FROM knowledge_vectors
                   WHERE user_id=? AND doc_id=? AND id=?""",
                (user_id, doc_id, int(chunk_id)),
            )
            db.commit()
        finally:
            db.close()

    async def recover_deleting_items(self, user_id: int) -> None:
        """崩溃恢复：重新入队正在删除的项"""
        await self.job_manager.recover_deleting_items(user_id, self.workflow_service)

    # ─── Internal ─────────────────────────────────────────────────────

    async def _assert_base_can_run_runtime_operation(self, user_id: int, base_id: str, operation: str) -> None:
        """断言知识库可以运行时操作"""
        base = KnowledgeBaseService.get_by_id(user_id, base_id)
        if not base:
            raise ValueError(f"Knowledge base not found: {base_id}")
        if base["status"] == "failed":
            raise ValueError(f"Knowledge base is in failed state; restore it before {operation}.")

    async def _assert_subtrees_can_reindex(self, user_id: int, base_id: str, root_ids: list[str]) -> None:
        """断言子树可以重新索引"""
        blocking_counts = {}
        for root_id in root_ids:
            subtree = KnowledgeItemService.get_subtree_items(user_id, base_id, [root_id], include_roots=True)
            for item in subtree:
                if item["status"] not in REINDEX_ALLOWED_STATUSES:
                    blocking_counts[item["status"]] = blocking_counts.get(item["status"], 0) + 1

        if blocking_counts:
            summary = ", ".join(f"{s}={c}" for s, c in sorted(blocking_counts.items()))
            raise ValueError(f"Cannot reindex knowledge item until the entire subtree is completed or failed: {summary}")


# 全局实例
knowledge_orchestration_service = KnowledgeOrchestrationService()
