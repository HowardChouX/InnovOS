"""MiniMax 视频生成 V2 适配器（Hailuo-03 / MiniMax-H3）。

MiniMax 非 OpenAI 兼容协议，用 httpx 直打 REST。异步任务模型：
- create_task: POST /v2/video_generation → {"task_id": ...}
- query_task:  GET  /v2/query/video_generation/{task_id}
               → {"task": {"status": ..., "content": {"url": ...}}}
  成功时 task.content.url 即视频下载地址（H3 无需 file_id 换取）。

实例不持有 api_key，每次调用传入。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "MiniMax-H3"


class MinimaxVideoError(Exception):
    """MiniMax 接口返回非 2xx，携带其 error message。"""


class MinimaxVideoAdapter:
    """MiniMax 视频生成 REST 适配器（即用即构造 client）。"""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @staticmethod
    def _extract_error_message(data: Any, status_code: int) -> str:
        """从 OpenAI 风格错误体提取 message。"""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
        return f"MiniMax API error (HTTP {status_code})"

    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        """创建文生视频任务，返回 MiniMax 侧 task_id。"""
        url = f"{api_host.rstrip('/')}/v2/video_generation"
        body = {
            "model": DEFAULT_MODEL,
            "content": [{"type": "text", "text": prompt}],
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(resp.json(), resp.status_code)
            )
        task_id = resp.json().get("task_id")
        if not task_id:
            raise MinimaxVideoError("MiniMax 未返回 task_id")
        return str(task_id)

    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict:
        """查询任务状态。返回 {status, video_url, error}。"""
        url = f"{api_host.rstrip('/')}/v2/query/video_generation/{remote_task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(resp.json(), resp.status_code)
            )
        task = resp.json().get("task", {})
        status = task.get("status", "")
        video_url = None
        if status == "succeeded":
            video_url = (task.get("content") or {}).get("url")
        error = task.get("error") if status in ("failed", "expired") else None
        return {"status": status, "video_url": video_url, "error": error}


minimax_video_adapter = MinimaxVideoAdapter()
