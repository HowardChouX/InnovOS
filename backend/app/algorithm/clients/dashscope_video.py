"""DashScope 百炼 Wan 2.7 文生视频适配器。

非 OpenAI 兼容协议，用 httpx 直打 REST。异步任务模型：
- create_task: POST .../services/aigc/video-generation/video-synthesis
               → {"output": {"task_id": ...}}
- query_task:  GET .../tasks/{task_id}
               → {"output": {"task_status": ..., "video_url": ...}}
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError

logger = logging.getLogger(__name__)

_API_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
_TASK_PATH = "/api/v1/tasks"


class DashScopeVideoError(VideoAdapterError):
    """DashScope 接口返回非 2xx，携带其错误信息。"""


class DashScopeVideoAdapter(VideoAdapter):
    protocol = "video_dashscope"
    default_model = "wan2.7-t2v-2026-06-12"

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def capabilities(self) -> dict[str, Any]:
        return {
            "resolutions": ["480P", "720P", "1080P"],
            "duration": {"min": 2, "max": 15},
            "ratios": ["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"],
        }

    @staticmethod
    def _normalize_base(api_host: str) -> str:
        """确保 api_host 不含尾部 /api/v1（由拼接时统一加）。"""
        host = api_host.rstrip("/")
        if host.endswith("/api/v1"):
            host = host[: -len("/api/v1")]
        return host

    @staticmethod
    def _extract_error(data: Any, status_code: int) -> str:
        if isinstance(data, dict):
            msg = data.get("message") or ""
            code = data.get("code") or ""
            if msg and code:
                return f"{code}: {msg}"
            if msg:
                return str(msg)
        return f"DashScope API error (HTTP {status_code})"

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return None

    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        model: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        base = self._normalize_base(api_host)
        url = f"{base}{_API_PATH}"
        body = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": resolution,
                "ratio": ratio,
                "duration": duration,
                "prompt_extend": True,
                "watermark": False,
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise DashScopeVideoError(
                self._extract_error(data, resp.status_code)
            )
        task_id = (data or {}).get("output", {}).get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise DashScopeVideoError("DashScope 未返回 task_id")
        return str(task_id)

    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict[str, Any]:
        base = self._normalize_base(api_host)
        url = f"{base}{_TASK_PATH}/{remote_task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise DashScopeVideoError(
                self._extract_error(data, resp.status_code)
            )
        output = (data or {}).get("output", {}) if isinstance(data, dict) else {}
        raw_status = (output.get("task_status") or "").upper()
        # 归一化
        STATUS_MAP = {
            "PENDING": "queued",
            "RUNNING": "running",
            "SUCCEEDED": "succeeded",
        }
        if raw_status in STATUS_MAP:
            status = STATUS_MAP[raw_status]
        else:
            status = "failed"
        video_url = output.get("video_url") if status == "succeeded" else None
        error = None
        if status == "failed":
            msg = output.get("message") or ""
            code = output.get("code") or ""
            error = f"{code}: {msg}" if code and msg else (msg or "unknown error")
        return {"status": status, "video_url": video_url, "error": error}


dashscope_video_adapter = DashScopeVideoAdapter()
