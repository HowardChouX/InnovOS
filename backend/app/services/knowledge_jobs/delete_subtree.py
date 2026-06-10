"""
Job handler for knowledge.delete-subtree — removes items and their vectors.

Input: {baseId: str, rootItemIds: list[str]}

Finds all subtree items, cancels active jobs touching those items, deletes
vectors from the vector store, and deletes items from the database.
"""
import json
import logging
from typing import Any, Optional

from app.algorithm.knowledge.vector_store import VectorStore
from app.database import get_db
from app.services.knowledge_job_manager import (
    JobHandler,
    JobSignal,
    JOB_PENDING,
    JOB_RUNNING,
)
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)


class DeleteSubtreeHandler(JobHandler):
    """Handles deletion of items and their vector store entries for a subtree."""

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

        # Find all subtree items (they should already have "deleting" status set by the workflow)
        subtree_items = KnowledgeItemService.get_subtree_items(
            user_id, base_id, root_item_ids, include_roots=True
        )
        if not subtree_items:
            logger.info("No subtree items found for deletion (base=%s)", base_id)
            return

        all_ids = [item["id"] for item in subtree_items]
        logger.info(
            "Deleting %d items (subtree roots=%s) from base %s",
            len(all_ids), root_item_ids, base_id,
        )

        # Cancel active jobs touching these items
        self._cancel_jobs_for_item_ids(base_id, all_ids, current_job_id=job_id)

        signal.throw_if_aborted()

        # Delete vectors for all items in the subtree
        store = VectorStore(user_id=user_id)
        store.delete_by_external_ids(all_ids)

        # Delete items from database
        KnowledgeItemService.delete_items_by_ids(user_id, base_id, all_ids)

        logger.info("Deleted %d items (subtree) from base %s", len(all_ids), base_id)

    def _cancel_jobs_for_item_ids(
        self, base_id: str, item_ids: list[str], current_job_id: Optional[str] = None
    ) -> None:
        """Cancel pending/running jobs whose input_data references any of the given item IDs."""
        item_set = set(item_ids)

        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, input_data FROM knowledge_jobs
                   WHERE queue=? AND status IN (?, ?)""",
                (base_id, JOB_PENDING, JOB_RUNNING),
            ).fetchall()

            for row in rows:
                jid = row["id"]
                if jid == current_job_id:
                    continue

                try:
                    inp = json.loads(row["input_data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                # Check if this job touches any of the items being deleted
                job_item_id = inp.get("itemId", "")
                job_item_ids = inp.get("rootItemIds", [])

                if job_item_id in item_set:
                    self.job_manager.cancel_job(jid, reason="item-deleted")
                elif any(iid in item_set for iid in (job_item_ids if isinstance(job_item_ids, list) else [])):
                    self.job_manager.cancel_job(jid, reason="item-deleted")
        finally:
            db.close()


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
