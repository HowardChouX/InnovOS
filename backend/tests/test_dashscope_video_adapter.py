"""DashScope Wan 2.7 视频适配器测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.dashscope_video import (
    DashScopeVideoAdapter,
    DashScopeVideoError,
)
from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return DashScopeVideoAdapter()


def test_adapter_is_video_adapter(adapter):
    assert isinstance(adapter, VideoAdapter)


def test_protocol_and_default_model(adapter):
    assert adapter.protocol == "video_dashscope"
    assert adapter.default_model == "wan2.7-t2v-2026-06-12"


def test_capabilities(adapter):
    caps = adapter.capabilities()
    assert "480P" in caps["resolutions"]
    assert "720P" in caps["resolutions"]
    assert "1080P" in caps["resolutions"]
    assert caps["duration"]["min"] == 2
    assert caps["duration"]["max"] == 15
    assert "16:9" in caps["ratios"]
    assert "9:16" in caps["ratios"]
    assert len(caps["ratios"]) == 6


def test_error_is_adapter_error():
    assert issubclass(DashScopeVideoError, VideoAdapterError)


async def test_create_task_sends_correct_request(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "tsk-123"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-ds",
            api_host="https://dashscope.aliyuncs.com/api/v1",
            model="wan2.7-t2v-2026-06-12",
            prompt="test video",
            resolution="720P",
            duration=10,
            ratio="16:9",
        )

    assert task_id == "tsk-123"
    call = mock_client.post.call_args
    assert call.args[0] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-ds"
    assert headers["X-DashScope-Async"] == "enable"
    body = call.kwargs["json"]
    assert body["model"] == "wan2.7-t2v-2026-06-12"
    assert body["input"]["prompt"] == "test video"
    assert body["parameters"]["resolution"] == "720P"
    assert body["parameters"]["ratio"] == "16:9"
    assert body["parameters"]["duration"] == 10
    assert body["parameters"]["prompt_extend"] is True
    assert body["parameters"]["watermark"] is False


async def test_create_task_with_custom_model(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "tsk-456"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-ds",
            api_host="https://dashscope.aliyuncs.com/api/v1",
            model="wan2.7-t2v-20260901",
            prompt="test",
            resolution="1080P",
            duration=15,
            ratio="21:9",
        )
    assert task_id == "tsk-456"
    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "wan2.7-t2v-20260901"


async def test_create_task_normalizes_api_host(adapter):
    """api_host 已含 /api/v1 时不应重复拼接。"""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "x"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        await adapter.create_task(
            api_key="sk",
            api_host="https://dashscope.aliyuncs.com",
            model="wan2.7",
            prompt="x",
            resolution="720P",
            duration=5,
            ratio="16:9",
        )
    url = mock_client.post.call_args.args[0]
    assert url == "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"


async def test_query_task_pending_maps_to_queued(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_status": "PENDING"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "queued"


async def test_query_task_running(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_status": "RUNNING"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "running"


async def test_query_task_succeeded_returns_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {"output": {"task_status": "SUCCEEDED", "video_url": "https://cdn.x.com/out.mp4"}},
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "succeeded"
    assert result["video_url"] == "https://cdn.x.com/out.mp4"


async def test_query_task_failed_returns_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "output": {
                    "task_status": "FAILED",
                    "message": "request rejected",
                    "code": "RateLimitExceeded",
                }
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "failed"
    assert result["error"] is not None


def _mock_bad_json_response(status_code: int):
    import json as _json
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(side_effect=_json.JSONDecodeError("Expecting value", "", 0))
    return resp


async def test_create_task_html_502_raises_dashscope_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=_mock_bad_json_response(502))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(DashScopeVideoError) as exc:
            await adapter.create_task(
                api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
                model="wan2.7", prompt="x", resolution="720P", duration=5, ratio="16:9",
            )
    assert "502" in str(exc.value)


async def test_query_task_html_504_raises_dashscope_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_bad_json_response(504))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(DashScopeVideoError) as exc:
            await adapter.query_task(
                api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
                remote_task_id="x",
            )
    assert "504" in str(exc.value)
