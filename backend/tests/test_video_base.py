"""VideoAdapter 基类 + 注册表测试。"""
import pytest
from app.algorithm.clients.video_base import (
    VideoAdapter,
    VideoAdapterError,
    VideoProtocolError,
    VideoRegistry,
)


class FakeAdapter(VideoAdapter):
    protocol = "video_fake"
    default_model = "fake-model"
    def capabilities(self):
        return {"resolutions": ["480P"], "duration": {"min": 2, "max": 10}, "ratios": ["16:9"]}
    async def create_task(self, **kwargs):
        return "fake-task-id"
    async def query_task(self, **kwargs):
        return {"status": "succeeded", "video_url": "https://x.mp4", "error": None}


def test_video_adapter_error_is_exception():
    assert issubclass(VideoAdapterError, Exception)


def test_video_protocol_error_is_exception():
    assert issubclass(VideoProtocolError, Exception)


def test_registry_register_and_get():
    VideoRegistry._registry = {}
    adapter = FakeAdapter()
    VideoRegistry.register(adapter)
    assert VideoRegistry.get("video_fake") is adapter


def test_registry_get_unknown_raises():
    VideoRegistry._registry = {}
    with pytest.raises(VideoProtocolError, match="video_unknown"):
        VideoRegistry.get("video_unknown")


def test_capabilities_structure():
    adapter = FakeAdapter()
    caps = adapter.capabilities()
    assert isinstance(caps["resolutions"], list)
    assert isinstance(caps["duration"], dict)
    assert "min" in caps["duration"] and "max" in caps["duration"]
    assert isinstance(caps["ratios"], list)
