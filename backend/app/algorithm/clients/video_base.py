"""VideoAdapter 抽象基类 + 注册表。

所有视频供应商适配器继承此基类，通过 VideoRegistry 按 protocol 分发。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class VideoAdapterError(Exception):
    """所有视频 adapter 的统一异常，携带归一化错误信息。"""


class VideoProtocolError(Exception):
    """protocol 未注册。"""


class VideoAdapter(ABC):
    """视频适配器抽象基类。"""

    protocol: str = ""
    default_model: str = ""

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """返回能力元数据：{resolutions: list[str], duration: {min, max}, ratios: list[str]}。"""

    @abstractmethod
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
        """创建文生视频任务，返回远端 task_id。"""

    @abstractmethod
    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict[str, Any]:
        """查询并归一化状态。返回 {status, video_url, error}。
        status ∈ pending/queued/running/succeeded/failed。"""


class VideoRegistry:
    _registry: dict[str, VideoAdapter] = {}

    @classmethod
    def register(cls, adapter: VideoAdapter) -> None:
        cls._registry[adapter.protocol] = adapter
        logger.info("视频适配器已注册: protocol=%s", adapter.protocol)

    @classmethod
    def get(cls, protocol: str) -> VideoAdapter:
        adapter = cls._registry.get(protocol)
        if adapter is None:
            raise VideoProtocolError(
                f"不支持的视频协议: {protocol}；"
                f"已注册: {list(cls._registry.keys())}"
            )
        return adapter


# ── 注册内置视频适配器 ──
from app.algorithm.clients.minimax_video import minimax_video_adapter
from app.algorithm.clients.dashscope_video import dashscope_video_adapter

VideoRegistry.register(minimax_video_adapter)
VideoRegistry.register(dashscope_video_adapter)
