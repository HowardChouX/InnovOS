"""
Knowledge Job Manager — 轻量级异步作业系统

职责：
- 作业排队（DB 持久化 + asyncio 触发）
- 重试策略（3次 + 指数退避）
- 超时控制
- 作业取消（asyncio.Event）
- 每库队列序列化
- 崩溃恢复
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from app.database import get_db

logger = logging.getLogger(__name__)

# ─── 作业状态 ──────────────────────────────────────────────
JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

# ─── Job 类型 ──────────────────────────────────────────────
JOB_TYPE_PREPARE_ROOT = "knowledge.prepare-root"
JOB_TYPE_INDEX_DOCUMENTS = "knowledge.index-documents"
JOB_TYPE_DELETE_SUBTREE = "knowledge.delete-subtree"
JOB_TYPE_REINDEX_SUBTREE = "knowledge.reindex-subtree"
JOB_TYPE_CHECK_PROCESSING_RESULT = "knowledge.check-file-processing-result"

KNOWLEDGE_JOB_TYPES = [
    JOB_TYPE_PREPARE_ROOT,
    JOB_TYPE_INDEX_DOCUMENTS,
    JOB_TYPE_DELETE_SUBTREE,
    JOB_TYPE_REINDEX_SUBTREE,
    JOB_TYPE_CHECK_PROCESSING_RESULT,
]

# ─── 默认重试策略 ──────────────────────────────────────────
DEFAULT_RETRY_POLICY: dict[str, Any] = {
    "max_attempts": 3,
    "backoff": "exponential",
    "base_delay_ms": 2000,
    "max_delay_ms": 60_000,
}

DEFAULT_TIMEOUT_MS = 10 * 60 * 1000  # 10分钟
INDEX_TIMEOUT_MS = 30 * 60 * 1000    # 30分钟


@dataclass
class JobRecord:
    """DB 中的作业记录"""
    id: str
    job_type: str
    queue: str
    input_data: str  # JSON
    status: str
    attempt: int
    max_attempts: int
    timeout_ms: int
    parent_job_id: Optional[str]
    idempotency_key: Optional[str]
    error: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class JobHandle:
    """运行中的作业句柄 — 提供取消能力"""
    job_id: str
    job_type: str
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self) -> None:
        self.cancel_event.set()


class KnowledgeJobManager:
    """知识库作业管理器"""

    def __init__(self):
        self._handles: dict[str, JobHandle] = {}
        self._base_locks: dict[str, asyncio.Lock] = {}
        self._pending_tasks: set[asyncio.Task] = set()
        self._handlers: dict[str, JobHandler] = {}

    # ─── Handler 注册 ─────────────────────────────────────

    def register_handler(self, job_type: str, handler: "JobHandler") -> None:
        self._handlers[job_type] = handler

    # ─── API ───────────────────────────────────────────────

    async def enqueue(
        self,
        job_type: str,
        input_data: dict[str, Any],
        *,
        queue: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        delay_ms: int = 0,
    ) -> str:
        """入队作业"""
        handler = self._handlers.get(job_type)
        if not handler:
            raise ValueError(f"Unknown job type: {job_type}")

        # 幂等性检查
        if idempotency_key:
            existing = self._find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Job already exists (idempotency): {idempotency_key}")
                return existing["id"]

        now = _now_iso()
        job_id = _generate_job_id(job_type)

        q = queue or "default"
        input_json = json.dumps(input_data, ensure_ascii=False)

        db = get_db()
        try:
            db.execute(
                """INSERT INTO knowledge_jobs
                   (id, job_type, queue, input_data, status, attempt, max_attempts,
                    timeout_ms, parent_job_id, idempotency_key, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id, job_type, q, input_json, JOB_PENDING, 0,
                    handler.max_attempts, handler.timeout_ms,
                    parent_job_id, idempotency_key, now, now,
                ),
            )
            db.commit()
        finally:
            db.close()

        # 延迟调度
        if delay_ms > 0:
            asyncio.get_event_loop().call_later(delay_ms / 1000, self._trigger_job, job_id)
        else:
            self._trigger_job(job_id)

        return job_id

    def _trigger_job(self, job_id: str) -> None:
        """创建后台任务执行作业"""
        task = asyncio.create_task(self._execute_job(job_id))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _execute_job(self, job_id: str) -> None:
        """执行单个作业（含重试逻辑）"""
        record = self._load_job(job_id)
        if not record or record.status != JOB_PENDING:
            return

        handler = self._handlers.get(record.job_type)
        if not handler:
            await self._fail_job(job_id, f"No handler for {record.job_type}")
            return

        # 串行化：每个队列同一时间只执行一个作业
        lock = self._get_base_lock(record.queue)
        async with lock:
            handle = JobHandle(job_id=job_id, job_type=record.job_type)
            self._handles[job_id] = handle

            try:
                for attempt in range(1, record.max_attempts + 1):
                    # 重新加载作业（可能在等待时被取消）
                    record = self._load_job(job_id)
                    if not record or record.status == JOB_CANCELLED:
                        return
                    if record.status == JOB_COMPLETED:
                        return

                    # 标记为 running
                    self._update_status(job_id, JOB_RUNNING, attempt=attempt)

                    # 创建信号包装
                    signal = JobSignal(handle.cancel_event)

                    # 带超时执行
                    try:
                        timeout_s = record.timeout_ms / 1000
                        await asyncio.wait_for(
                            handler.execute(job_id, json.loads(record.input_data), signal),
                            timeout=timeout_s,
                        )
                        self._update_status(job_id, JOB_COMPLETED)
                        await handler.on_settled(job_id, JOB_COMPLETED, None)
                        logger.info(f"Job {job_id} ({record.job_type}) completed")
                        return
                    except asyncio.TimeoutError:
                        error_msg = f"Job timed out after {record.timeout_ms}ms"
                        logger.warning(f"Job {job_id} timeout: {error_msg}")
                        if attempt < record.max_attempts:
                            delay = _compute_backoff(attempt, record.max_attempts)
                            logger.info(f"Retrying job {job_id} in {delay}ms (attempt {attempt}/{record.max_attempts})")
                            self._update_status(job_id, JOB_PENDING, error=error_msg)
                            await asyncio.sleep(delay / 1000)
                        else:
                            await self._fail_job(job_id, error_msg, handler)
                    except asyncio.CancelledError:
                        self._update_status(job_id, JOB_CANCELLED)
                        await handler.on_settled(job_id, JOB_CANCELLED, None)
                        return
                    except Exception as e:
                        error_msg = f"{type(e).__name__}: {e}"
                        logger.warning(f"Job {job_id} failed: {error_msg}")
                        if attempt < record.max_attempts:
                            delay = _compute_backoff(attempt, record.max_attempts)
                            logger.info(f"Retrying job {job_id} in {delay}ms (attempt {attempt}/{record.max_attempts})")
                            self._update_status(job_id, JOB_PENDING, error=error_msg)
                            await asyncio.sleep(delay / 1000)
                        else:
                            await self._fail_job(job_id, error_msg, handler)
            finally:
                self._handles.pop(job_id, None)

    def cancel_job(self, job_id: str, reason: str = "cancelled") -> None:
        """取消作业"""
        handle = self._handles.get(job_id)
        if handle:
            handle.cancel()
            logger.info(f"Cancelled active job {job_id}: {reason}")
        # 更新 DB 状态（如果未运行）
        self._update_status(job_id, JOB_CANCELLED, error=reason)

    def cancel_jobs_for_base(self, base_id: str, current_job_id: Optional[str] = None, reason: str = "base-operation") -> None:
        """取消指定知识库的所有活跃作业"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT id FROM knowledge_jobs
                   WHERE queue=? AND status IN (?, ?)""",
                (base_id, JOB_PENDING, JOB_RUNNING),
            ).fetchall()
            for row in rows:
                jid = row["id"]
                if jid != current_job_id:
                    self.cancel_job(jid, reason)
        finally:
            db.close()

    def list_active_jobs(self, queue: str) -> list[dict[str, Any]]:
        """列出队列中的活跃作业"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, job_type, input_data, status, attempt, parent_job_id
                   FROM knowledge_jobs
                   WHERE queue=? AND status IN (?, ?)
                   ORDER BY created_at""",
                (queue, JOB_PENDING, JOB_RUNNING),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    async def recover_deleting_items(self, user_id: int, workflow_service) -> None:
        """崩溃恢复：重新入队正在删除的项"""
        from app.services.knowledge_item_service import KnowledgeItemService

        try:
            deleting_groups = KnowledgeItemService.get_deleting_root_groups(user_id)
        except Exception as e:
            logger.error(f"Failed to scan deleting items for recovery: {e}")
            return

        if not deleting_groups:
            return

        for group in deleting_groups:
            for i in range(0, len(group["rootItemIds"]), 100):
                chunk = group["rootItemIds"][i:i + 100]
                try:
                    await self.enqueue(
                        JOB_TYPE_DELETE_SUBTREE,
                        {"baseId": group["baseId"], "rootItemIds": chunk},
                        queue=group["baseId"],
                    )
                except Exception as e:
                    logger.error(f"Failed to enqueue recovered delete: {e}")

    def recover_stalled_jobs(self) -> None:
        """恢复卡住的作业（进程崩溃后）"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, job_type, input_data, queue
                   FROM knowledge_jobs
                   WHERE status=?""",
                (JOB_RUNNING,),
            ).fetchall()
            for row in rows:
                logger.info(f"Recovering stalled job {row['id']} ({row['job_type']})")
                self._update_status(row["id"], JOB_PENDING)
                self._trigger_job(row["id"])
        finally:
            db.close()

    # ─── 内部方法 ──────────────────────────────────────────

    def _get_base_lock(self, queue: str) -> asyncio.Lock:
        if queue not in self._base_locks:
            self._base_locks[queue] = asyncio.Lock()
        return self._base_locks[queue]

    def _load_job(self, job_id: str) -> Optional[JobRecord]:
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row:
                return None
            return JobRecord(**dict(row))
        finally:
            db.close()

    def _update_status(
        self, job_id: str, status: str,
        attempt: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        db = get_db()
        try:
            now = _now_iso()
            if attempt is not None and error is not None:
                db.execute(
                    """UPDATE knowledge_jobs
                       SET status=?, attempt=?, error=?, updated_at=?
                       WHERE id=?""",
                    (status, attempt, error, now, job_id),
                )
            elif attempt is not None:
                db.execute(
                    """UPDATE knowledge_jobs
                       SET status=?, attempt=?, updated_at=?
                       WHERE id=?""",
                    (status, attempt, now, job_id),
                )
            elif error is not None:
                db.execute(
                    """UPDATE knowledge_jobs
                       SET status=?, error=?, updated_at=?
                       WHERE id=?""",
                    (status, error, now, job_id),
                )
            else:
                db.execute(
                    """UPDATE knowledge_jobs
                       SET status=?, updated_at=?
                       WHERE id=?""",
                    (status, now, job_id),
                )
            db.commit()
        finally:
            db.close()

    async def _fail_job(self, job_id: str, error: str, handler: Optional["JobHandler"] = None) -> None:
        self._update_status(job_id, JOB_FAILED, error=error)
        logger.error(f"Job {job_id} failed: {error}")
        if handler:
            await handler.on_settled(job_id, JOB_FAILED, error)

    def _find_by_idempotency_key(self, key: str) -> Optional[dict[str, Any]]:
        db = get_db()
        try:
            row = db.execute(
                """SELECT id FROM knowledge_jobs
                   WHERE idempotency_key=? AND status NOT IN (?, ?)""",
                (key, JOB_FAILED, JOB_CANCELLED),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()


class JobSignal:
    """作业信号 — 类似 AbortSignal"""
    def __init__(self, cancel_event: asyncio.Event):
        self._cancel_event = cancel_event

    @property
    def aborted(self) -> bool:
        return self._cancel_event.is_set()

    def throw_if_aborted(self) -> None:
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Job was cancelled")


class JobHandler:
    """作业处理器基类"""
    def __init__(
        self,
        max_attempts: int = 3,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ):
        self.max_attempts = max_attempts
        self.timeout_ms = timeout_ms

    async def execute(self, job_id: str, input_data: dict[str, Any], signal: JobSignal) -> None:
        raise NotImplementedError

    async def on_settled(self, job_id: str, status: str, error: Optional[str]) -> None:
        """作业最终状态回调（成功或重试用尽）"""
        pass


# ─── 工具函数 ──────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_job_id(job_type: str) -> str:
    import uuid
    prefix = job_type.replace("knowledge.", "kj-")
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _compute_backoff(attempt: int, max_attempts: int) -> int:
    """指数退避：2s, 4s, 8s, ... cap at 60s"""
    delay = 2000 * (2 ** (attempt - 1))
    return min(delay, 60_000)


def knowledge_queue_name(base_id: str) -> str:
    return base_id


def knowledge_idempotency_key(prefix: str, *parts: str) -> str:
    """生成幂等键"""
    key_parts = [prefix] + list(parts)
    return ":".join(key_parts)
