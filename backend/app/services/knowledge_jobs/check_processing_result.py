"""
Job handler for knowledge.check-file-processing-result — polls external file processing APIs.

Input: {baseId: str, itemId: str, taskId: str, processorId: str}

Polls the external processor for completion.
When done, indexes the extracted content into vector store.
On failure after max attempts, marks item as failed.
"""
import json
import logging
from typing import Optional

from app.algorithm.knowledge.pipeline import KnowledgePipeline
from app.algorithm.knowledge.processors import file_processor_registry
from app.database import get_db
from app.services.knowledge_job_manager import (
    JobHandler,
    JobSignal,
    JOB_TYPE_CHECK_PROCESSING_RESULT,
    knowledge_queue_name,
    knowledge_idempotency_key,
)
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)


class CheckProcessingResultHandler(JobHandler):
    """Polls external file processing API for completion, then indexes content."""

    def __init__(self, job_manager, knowledge_lock_manager):
        super().__init__(max_attempts=30, timeout_ms=120 * 1000)  # 30 attempts, 2min each
        self.job_manager = job_manager
        self.lock_manager = knowledge_lock_manager

    async def execute(self, job_id: str, input_data: dict, signal: JobSignal) -> None:
        base_id = input_data["baseId"]
        item_id = input_data["itemId"]
        task_id = input_data["taskId"]
        processor_id = input_data["processorId"]
        attempt = input_data.get("attempt", 0)

        user_id = _get_user_id_from_base(base_id)

        item = KnowledgeItemService.get_by_id(user_id, item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")

        if item["status"] == "deleting":
            logger.info("Item %s is being deleted — skipping check-processing-result", item_id)
            return

        # Find the processor
        processor = file_processor_registry.get(processor_id)

        signal.throw_if_aborted()

        # Poll external API
        try:
            result = await processor.poll(task_id)
        except Exception as e:
            logger.warning("Poll failed for task %s: %s", task_id, e)
            result = None

        if result is None:
            # Still processing — re-enqueue self with delay (max 30 attempts = ~5 min total)
            next_attempt = attempt + 1
            if next_attempt >= self.max_attempts:
                logger.error("External processing max attempts reached for item %s", item_id)
                await self._set_status_under_lock(base_id, user_id, item_id, "failed", "External processing timed out")
                return

            input_data["attempt"] = next_attempt
            await self.job_manager.enqueue(
                JOB_TYPE_CHECK_PROCESSING_RESULT,
                input_data,
                queue=knowledge_queue_name(base_id),
                idempotency_key=knowledge_idempotency_key("check-processing", base_id, item_id, str(next_attempt)),
                parent_job_id=job_id,
                delay_ms=5000,  # Poll every 5 seconds
            )
            logger.info(
                "Re-enqueued check-processing for item %s (attempt %d/%d)",
                item_id,
                next_attempt,
                self.max_attempts,
            )
            return

        # Processing completed — proceed to index
        signal.throw_if_aborted()

        await self._set_status_under_lock(base_id, user_id, item_id, "embedding")

        pipeline = KnowledgePipeline(user_id, base_id)
        chunk_count = await pipeline.index_item(item_id, result["content"])
        logger.info("External processed item %s indexed (%d chunks)", item_id, chunk_count)

        signal.throw_if_aborted()

        await self._set_status_under_lock(base_id, user_id, item_id, "completed")

    async def _set_status_under_lock(
        self,
        base_id: str,
        user_id: int,
        item_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        async def _update():
            KnowledgeItemService.update_status(user_id, item_id, status, error or "")

        await self.lock_manager.with_base_mutation_lock(base_id, _update)

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
        KnowledgeItemService.update_status(user_id, item_id, "failed", error or "External processing failed")
    finally:
        db.close()
