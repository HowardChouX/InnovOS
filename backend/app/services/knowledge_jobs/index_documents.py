"""
Job handler for knowledge.index-documents — processes leaf items (file/note/url).

Input: {baseId: str, itemId: str}

For files: uses file processor (sync local or async external with polling).
For notes: extracts text from data.content/text, indexes via pipeline.index_item().
For urls: fetches URL content via httpx, indexes via pipeline.index_item().
"""
import json
import logging
import os
from typing import Optional

from app.algorithm.knowledge.pipeline import KnowledgePipeline
from app.algorithm.knowledge.processors import file_processor_registry
from app.database import get_db
from app.services.knowledge_job_manager import (
    JobHandler,
    JobSignal,
    JOB_TYPE_CHECK_PROCESSING_RESULT,
    knowledge_idempotency_key,
    knowledge_queue_name,
)
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)


class IndexDocumentsHandler(JobHandler):
    """Handles leaf items (file/note/url) by reading content and indexing into vector store."""

    def __init__(self, job_manager, knowledge_lock_manager):
        super().__init__(max_attempts=3, timeout_ms=30 * 60 * 1000)
        self.job_manager = job_manager
        self.lock_manager = knowledge_lock_manager

    async def execute(self, job_id: str, input_data: dict, signal: JobSignal) -> None:
        base_id = input_data["baseId"]
        item_id = input_data["itemId"]
        user_id = _get_user_id_from_base(base_id)

        item = KnowledgeItemService.get_by_id(user_id, item_id)
        if not item:
            raise ValueError(f"Knowledge item not found: {item_id}")

        if item["status"] == "deleting":
            logger.info("Item %s is being deleted — skipping index-documents", item_id)
            return

        item_type = item["type"]
        if item_type not in ("file", "note", "url"):
            logger.info("Unknown item type '%s' for item %s — marking completed", item_type, item_id)
            await self._set_status_under_lock(base_id, user_id, item_id, "completed")
            return

        # Set status to reading
        await self._set_status_under_lock(base_id, user_id, item_id, "reading")

        signal.throw_if_aborted()

        data = item.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}

        pipeline = KnowledgePipeline(user_id, base_id)

        if item_type == "file":
            file_path = data.get("path") or data.get("source", "")
            file_name = data.get("originalName") or os.path.basename(file_path)

            if not file_path or not os.path.exists(file_path):
                logger.warning("File not found for item %s: %s", item_id, file_path)
                await self._set_status_under_lock(base_id, user_id, item_id, "failed", "File not found")
                return

            # Resolve file processor (全局设置 → KB 设置 → 默认)
            db = get_db()
            try:
                base_row = db.execute(
                    "SELECT file_processor_id FROM knowledge_bases WHERE id=? AND user_id=?",
                    (base_id, user_id),
                ).fetchone()
                # 检查全局设置
                global_row = db.execute(
                    "SELECT value FROM system_settings WHERE key=?",
                    ("file_processor",),
                ).fetchone()
            finally:
                db.close()

            processor_id = base_row["file_processor_id"] if base_row and base_row["file_processor_id"] else None
            if not processor_id and global_row and global_row["value"]:
                processor_id = global_row["value"]
            processor = file_processor_registry.get(processor_id)

            if processor.is_async():
                # External file processor — async path
                try:
                    task_id = await processor.submit(file_path)
                except Exception as e:
                    logger.error("Failed to submit file to external processor: %s", e)
                    await self._set_status_under_lock(
                        base_id, user_id, item_id, "failed", f"External processor submission failed: {e}"
                    )
                    return

                # Store task info in item data
                item_data = data.copy()
                item_data["externalTaskId"] = task_id
                item_data["externalProcessorId"] = processor_id
                db = get_db()
                try:
                    db.execute(
                        "UPDATE knowledge_items SET data=?, updated_at=? WHERE id=?",
                        (json.dumps(item_data), _now_iso(), item_id),
                    )
                    db.commit()
                finally:
                    db.close()

                # Enqueue polling job
                await self.job_manager.enqueue(
                    JOB_TYPE_CHECK_PROCESSING_RESULT,
                    {"baseId": base_id, "itemId": item_id, "taskId": task_id, "processorId": processor_id, "attempt": 0},
                    queue=knowledge_queue_name(base_id),
                    idempotency_key=knowledge_idempotency_key("check-processing", base_id, item_id),
                )
                logger.info("Submitted file %s to external processor %s: task=%s", file_name, processor_id, task_id)
                return  # Don't mark completed yet — polling job will

            # Sync processor path — parse file first
            result = await processor.process(file_path, file_name)

            # Save parsed content to item data
            item_data = data.copy()
            item_data["parsedContent"] = result["content"]
            item_data["parsedTitle"] = result.get("title", file_name)
            db = get_db()
            try:
                db.execute(
                    "UPDATE knowledge_items SET data=?, updated_at=? WHERE id=?",
                    (json.dumps(item_data), _now_iso(), item_id),
                )
                db.commit()
            finally:
                db.close()

            # Embedding is REQUIRED — if embedding model is unavailable or fails,
            # exception propagates → job retries → on_settled marks item 'failed'
            # (CherryStudio behavior: embedding failure → item fails → user reindexes)
            chunk_count = await pipeline.index_item(item_id, result["content"])
            logger.info("File item %s indexed (%d chunks)", item_id, chunk_count)

        elif item_type == "note":
            text = data.get("text") or data.get("content") or ""
            # Embedding is REQUIRED — if it fails, exception propagates → job retries → marks failed
            chunk_count = await pipeline.index_item(item_id, text)
            logger.info("Note item %s indexed (%d chunks)", item_id, chunk_count)

        elif item_type == "url":
            url = data.get("url") or data.get("sourceUrl") or ""
            if not url:
                logger.warning("URL item %s has no URL in data", item_id)
                await self._set_status_under_lock(base_id, user_id, item_id, "failed", "No URL in item data")
                return

            # ── MarkDownload 融合管线：智能抓取 + 增强转换 ──
            from app.algorithm.knowledge.url_fetcher import fetch_url
            from app.algorithm.knowledge.html_to_markdown import url_to_markdown

            try:
                # Step 1: 智能抓取（httpx → Playwright → Node.js 三层降级）
                fetch_result = await fetch_url(url, timeout=30.0, use_browser_fallback=True)
                raw = fetch_result["html"]
                final_url = fetch_result["final_url"]

                if not raw or len(raw) < 50:
                    raise ValueError(f"抓取内容过少（{len(raw or '')} bytes）")

                logger.info(
                    "URL 抓取成功 [%s]: %s (%d bytes)",
                    fetch_result.get("fetcher", "?"), final_url, len(raw),
                )

                # Step 2: 转换为 Markdown
                if fetch_result.get("already_markdown"):
                    content = raw  # Node.js 已转换完成
                else:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    content = await loop.run_in_executor(
                        None, lambda: url_to_markdown(raw, base_url=final_url)
                    )

                # 兜底：内容太少则做纯文本提取
                if not content or len(content) < 20:
                    import re
                    logger.warning("转换内容过少，使用纯文本回退")
                    content = re.sub(r"<[^>]+>", " ", raw)
                    content = re.sub(r"\s+", " ", content).strip()

            except Exception as e:
                logger.warning("URL 抓取/转换失败 %s: %s", url, e)
                await self._set_status_under_lock(base_id, user_id, item_id, "failed", f"URL fetch/convert failed: {e}")
                return

            # Save fetched content to item data for LIKE search fallback
            item_data = data.copy()
            item_data["fetchedContent"] = content
            item_data["fetchedAt"] = _now_iso()
            item_data["fetchedUrl"] = final_url
            item_data["fetcher"] = fetch_result.get("fetcher", "httpx")
            db = get_db()
            try:
                db.execute(
                    "UPDATE knowledge_items SET data=?, updated_at=? WHERE id=?",
                    (json.dumps(item_data), _now_iso(), item_id),
                )
                db.commit()
            finally:
                db.close()

            # Embedding is REQUIRED
            chunk_count = await pipeline.index_item(item_id, content)
            logger.info("URL item %s indexed (%d chunks): %s", item_id, chunk_count, url)

        signal.throw_if_aborted()

        await self._set_status_under_lock(base_id, user_id, item_id, "completed")

    async def _set_status_under_lock(
        self, base_id: str, user_id: int, item_id: str, status: str, error: Optional[str] = None
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
        KnowledgeItemService.update_status(user_id, item_id, "failed", error or "Job failed")
    finally:
        db.close()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
