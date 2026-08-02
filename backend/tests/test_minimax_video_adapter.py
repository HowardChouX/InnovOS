"""MiniMax 视频适配器测试 — mock httpx.AsyncClient。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.minimax_video import (
    MinimaxVideoAdapter,
    MinimaxVideoError,
)


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return MinimaxVideoAdapter()


async def test_create_task_posts_and_returns_task_id(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"task_id": "424010985738629"})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            prompt="一个男孩在海边打篮球",
            resolution="2K",
            duration=5,
            ratio="16:9",
        )

    assert task_id == "424010985738629"
    # 验证请求 URL 与 body
    call = mock_client.post.call_args
    assert call.args[0] == "https://api.minimaxi.com/v2/video_generation"
    body = call.kwargs["json"]
    assert body["model"] == "MiniMax-H3"
    assert body["content"] == [{"type": "text", "text": "一个男孩在海边打篮球"}]
    assert body["resolution"] == "2K"
    assert body["duration"] == 5
    assert body["ratio"] == "16:9"
    # Bearer 鉴权
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test"


async def test_create_task_raises_on_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            422,
            {
                "type": "error",
                "error": {
                    "type": "unprocessable_entity_error",
                    "message": "video description contains sensitive content (1026)",
                },
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(MinimaxVideoError) as exc:
            await adapter.create_task(
                api_key="sk-test",
                api_host="https://api.minimaxi.com",
                prompt="x",
                resolution="2K",
                duration=5,
                ratio="16:9",
            )
    assert "sensitive content" in str(exc.value)


async def test_query_task_succeeded_returns_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "task": {
                    "id": "424010985738629",
                    "status": "succeeded",
                    "content": {"url": "https://cdn.example.com/out.mp4"},
                }
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            remote_task_id="424010985738629",
        )

    assert result["status"] == "succeeded"
    assert result["video_url"] == "https://cdn.example.com/out.mp4"
    assert result["error"] is None
    # 验证 GET URL
    assert (
        mock_client.get.call_args.args[0]
        == "https://api.minimaxi.com/v2/query/video_generation/424010985738629"
    )


async def test_query_task_running_has_no_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "running"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            remote_task_id="x",
        )

    assert result["status"] == "running"
    assert result["video_url"] is None
