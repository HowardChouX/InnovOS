"""
Job handler for knowledge.prepare-root — processes directory container items.

Input: {baseId: str, itemId: str}

Creates child items for each file in the directory's files_meta and enqueues
knowledge.index-documents for each child via the job manager.
"""
import json
import logging
import os
from typing import Optional

from app.database import get_db
from app.services.knowledge_job_manager import JobHandler, JobSignal
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)


class PrepareRootHandler(JobHandler):
    """Handles directory container items by creating child items and enqueueing index jobs."""

    def __init__(self, job_manager):
        super().__init__(max_attempts=3, timeout_ms=10 * 60 * 1000)
        self.job_manager = job_manager

    async def execute(self, job_id: str, input_data: dict, signal: JobSignal) -> None:
        base_id = input_data["baseId"]
        item_id = input_data["itemId"]
        user_id = _get_user_id_from_base(base_id)

        item = KnowledgeItemService.get_by_id(user_id, item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")

        if item["status"] == "deleting":
            logger.info("Item %s is being deleted — skipping prepare-root", item_id)
            return

        KnowledgeItemService.update_status(user_id, item_id, "preparing")

        data = item.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}

        upload_dir = data.get("uploadDir", "")
        tree = data.get("tree", [])

        if not upload_dir or not os.path.isdir(upload_dir):
            raise ValueError(f"Upload directory not found or not a directory: {upload_dir}")

        if not tree:
            logger.warning("Empty tree in directory item %s — marking completed", item_id)
            KnowledgeItemService.update_status(user_id, item_id, "completed")
            return

        signal.throw_if_aborted()

        leaf_count = await self._process_tree(
            user_id, base_id, item_id, tree, upload_dir, signal, job_id
        )

        KnowledgeItemService.update_status(user_id, item_id, "completed")
        logger.info("Directory item %s processed (%d leaves)", item_id, leaf_count)

    async def _process_tree(
        self, user_id: int, base_id: str, parent_id: str,
        nodes: list[dict], upload_dir: str, signal: JobSignal, job_id: str,
    ) -> int:
        """递归处理目录树节点，返回叶子节点（文件）数量。"""
        leaf_count = 0
        for node in nodes:
            signal.throw_if_aborted()

            name = node.get("name", "")
            if name.startswith("."):
                continue  # 跳过隐藏文件/目录

            if node["type"] == "file":
                full_path = node.get("path", "")
                original_name = node.get("originalName", name)
                if not full_path or not os.path.exists(full_path):
                    logger.warning("File not found: %s — skipping", full_path)
                    continue

                child = KnowledgeItemService.create(user_id, base_id, {
                    "type": "file",
                    "data": {"path": full_path, "originalName": original_name},
                    "groupId": parent_id,
                })
                if not child:
                    logger.warning("Failed to create child item for %s", name)
                    continue

                await self.job_manager.enqueue(
                    "knowledge.index-documents",
                    {"baseId": base_id, "itemId": child["id"]},
                    queue=base_id,
                    parent_job_id=job_id,
                )
                leaf_count += 1

            elif node["type"] == "directory":
                children = node.get("children", [])
                if not children:
                    continue  # 空目录跳过

                # 创建子 directory 项
                child_dir = KnowledgeItemService.create(user_id, base_id, {
                    "type": "directory",
                    "data": {"source": name, "name": name, "treeNode": node},
                    "groupId": parent_id,
                })
                if not child_dir:
                    logger.warning("Failed to create child directory item for %s", name)
                    continue

                # 递归处理子目录
                sub_leaves = await self._process_tree(
                    user_id, base_id, child_dir["id"],
                    children, upload_dir, signal, job_id,
                )
                if sub_leaves > 0:
                    KnowledgeItemService.update_status(user_id, child_dir["id"], "completed")
                leaf_count += sub_leaves

        return leaf_count

    async def on_settled(self, job_id: str, status: str, error: Optional[str]) -> None:
        if status != "failed":
            return
        _mark_item_failed(job_id, error)


def _get_user_id_from_base(base_id: str) -> int:
    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id FROM knowledge_bases WHERE id=?", (base_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Knowledge base not found: {base_id}")
        return row["user_id"]
    finally:
        db.close()


def _mark_item_failed(job_id: str, error: Optional[str]) -> None:
    db = get_db()
    try:
        row = db.execute(
            "SELECT input_data FROM knowledge_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row:
            return
        input_data = json.loads(row["input_data"])
        item_id = input_data.get("itemId", "")
        base_id = input_data.get("baseId", "")
        if not item_id or not base_id:
            return
        user_id = _get_user_id_from_base(base_id)
        KnowledgeItemService.update_status(user_id, item_id, "failed", error or "Job failed")
    finally:
        db.close()
