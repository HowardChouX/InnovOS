"""
Job handler for knowledge.reindex-subtree — resets and re-enqueues items.

Input: {baseId: str, rootItemIds: list[str]}

Checks no items are in "deleting" status (skips if so). Deletes vectors for
leaf items, deletes descendant items for container roots, resets root status,
and enqueues prepare-root or index-documents for each root.
"""
import json
import logging
from typing import Any, Optional

from app.algorithm.knowledge.vector_store import VectorStore
from app.database import get_db
from app.services.knowledge_job_manager import JobHandler, JobSignal
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)


class ReindexSubtreeHandler(JobHandler):
    """Handles reindexing of items by resetting status, deleting vectors/children, and re-enqueuing."""

    def __init__(self, job_manager):
        super().__init__(max_attempts=3, timeout_ms=10 * 60 * 1000)
        self.job_manager = job_manager

    async def execute(self, job_id: str, input_data: dict, signal: JobSignal) -> None:
        base_id = input_data["baseId"]
        root_item_ids: list[str] = input_data.get("rootItemIds", [])
        user_id = _get_user_id_from_base(base_id)

        if not root_item_ids:
            return

        signal.throw_if_aborted()

        # Check for "deleting" items — skip the entire operation if any root is being deleted
        for rid in root_item_ids:
            item = KnowledgeItemService.get_by_id(user_id, rid)
            if item and item["status"] == "deleting":
                logger.info(
                    "Root item %s is being deleted — skipping reindex-subtree for base %s",
                    rid, base_id,
                )
                return

        # Get all items in the subtrees (including roots)
        subtree_items = KnowledgeItemService.get_subtree_items(
            user_id, base_id, root_item_ids, include_roots=True
        )
        if not subtree_items:
            return

        # Classify roots by type
        roots: list[dict[str, Any]] = []
        for rid in root_item_ids:
            item = KnowledgeItemService.get_by_id(user_id, rid)
            if item:
                roots.append(item)

        container_roots = [r for r in roots if r["type"] == "directory"]
        leaf_roots = [r for r in roots if r["type"] in ("file", "note", "url")]

        # Collect all leaf items for vector deletion
        leaf_items = [it for it in subtree_items if it["type"] in ("file", "note", "url")]

        signal.throw_if_aborted()

        # Delete vectors for all leaf items
        store = VectorStore(user_id=user_id)
        store.delete_by_external_ids([it["id"] for it in leaf_items])

        # For container roots: delete descendant items (children will be recreated by prepare-root)
        for container in container_roots:
            descendants = KnowledgeItemService.get_subtree_items(
                user_id, base_id, [container["id"]], include_roots=False
            )
            if descendants:
                desc_ids = [d["id"] for d in descendants]
                KnowledgeItemService.delete_items_by_ids(user_id, base_id, desc_ids)

        signal.throw_if_aborted()

        # Reset root status and re-enqueue
        for root in roots:
            if root["type"] == "directory":
                KnowledgeItemService.update_status(user_id, root["id"], "preparing")
                await self.job_manager.enqueue(
                    "knowledge.prepare-root",
                    {"baseId": base_id, "itemId": root["id"]},
                    queue=base_id,
                    parent_job_id=job_id,
                )
            else:
                KnowledgeItemService.update_status(user_id, root["id"], "processing")
                await self.job_manager.enqueue(
                    "knowledge.index-documents",
                    {"baseId": base_id, "itemId": root["id"]},
                    queue=base_id,
                    parent_job_id=job_id,
                )

        logger.info(
            "Reindex initiated for %d roots in base %s",
            len(roots), base_id,
        )

    async def on_settled(self, job_id: str, status: str, error: Optional[str]) -> None:
        if status != "failed":
            return
        _mark_active_roots_failed(job_id, error)


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


def _mark_active_roots_failed(job_id: str, error: Optional[str]) -> None:
    """Mark roots that are still in an active (non-terminal) status as failed."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT input_data FROM knowledge_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row:
            return
        input_data = json.loads(row["input_data"])
        base_id = input_data.get("baseId", "")
        root_item_ids: list[str] = input_data.get("rootItemIds", [])
        if not base_id or not root_item_ids:
            return
        user_id = _get_user_id_from_base(base_id)

        terminal_statuses = {"completed", "failed", "deleting"}
        for rid in root_item_ids:
            item = KnowledgeItemService.get_by_id(user_id, rid)
            if item and item["status"] not in terminal_statuses:
                KnowledgeItemService.update_status(
                    user_id, rid, "failed", error or "Reindex failed"
                )
    finally:
        db.close()
