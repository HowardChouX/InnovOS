"""后台视频任务轮询器。

startup 启动 asyncio 循环，每 interval_seconds 秒扫描未终态任务，
向 MiniMax 查询并回写状态。用户离开页面任务仍推进。
"""
from __future__ import annotations

import asyncio
import logging

from app.algorithm.clients.minimax_video import (
    MinimaxVideoError,
    minimax_video_adapter,
)
from app.services.video_task_service import video_task_service

logger = logging.getLogger(__name__)

MINIMAX_PROVIDER_ID = "minimax"
TERMINAL_STATUSES = {"succeeded", "failed", "expired"}


def _lease_minimax_key() -> tuple[str | None, str | None]:
    from app.database import db_session
    from app.services.api_key_service import get_api_key_service

    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=MINIMAX_PROVIDER_ID)
    if not lease:
        return None, None
    with db_session() as db:
        row = db.execute(
            "SELECT api_host FROM model_providers WHERE provider_id = ?",
            (MINIMAX_PROVIDER_ID,),
        ).fetchone()
    api_host = row["api_host"] if row else "https://api.minimaxi.com"
    return lease.plaintext, api_host


class VideoPoller:
    def __init__(self, interval_seconds: float = 5.0) -> None:
        self._interval = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("视频轮询器已启动 (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("视频轮询器已停止")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"视频轮询轮次异常: {exc}")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def poll_once(self) -> int:
        """执行一轮轮询，返回回写的任务数。"""
        active = video_task_service.list_active()
        if not active:
            return 0

        api_key, api_host = _lease_minimax_key()
        if not api_key:
            logger.debug("无 MiniMax 密钥，跳过本轮轮询")
            return 0

        count = 0
        for task in active:
            remote_id = task.get("remoteTaskId")
            if not remote_id:
                continue
            try:
                result = await minimax_video_adapter.query_task(
                    api_key=api_key, api_host=api_host, remote_task_id=remote_id
                )
            except (MinimaxVideoError, Exception) as exc:  # noqa: BLE001
                logger.warning(f"查询任务 {task['id']} 失败: {exc}")
                continue
            video_task_service.apply_remote_status(
                task["id"],
                status=result["status"],
                video_url=result["video_url"],
                error=result["error"],
            )
            count += 1
        return count


video_poller = VideoPoller()
