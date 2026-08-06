"""MiniMax 视频适配器测试 — 继承 VideoAdapter 基类。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.minimax_video import (
    MinimaxVideoAdapter,
    MinimaxVideoError,
)
from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return MinimaxVideoAdapter()


def test_adapter_is_video_adapter(adapter):
    assert isinstance(adapter, VideoAdapter)


def test_protocol_and_default_model(adapter):
    assert adapter.protocol == "video_minimax"
    assert adapter.default_model == "MiniMax-H3"


def test_capabilities(adapter):
    caps = adapter.capabilities()
    assert "768P" in caps["resolutions"]
    assert "2K" in caps["resolutions"]
    assert caps["duration"]["min"] == 4
    assert caps["duration"]["max"] == 15
    assert "16:9" in caps["ratios"]
    assert len(caps["ratios"]) == 6


def test_minimax_error_is_adapter_error():
    assert issubclass(MinimaxVideoError, VideoAdapterError)


async def test_create_task_passes_model(adapter):
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
            model="MiniMax-H3",
            prompt="一个男孩在海边打篮球",
            resolution="2K",
            duration=5,
            ratio="16:9",
        )

    assert task_id == "424010985738629"
    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "MiniMax-H3"


async def test_create_task_uses_custom_model(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"task_id": "x"})
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
            model="MiniMax-H3-20260901",
            prompt="test",
            resolution="768P",
            duration=5,
            ratio="16:9",
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "MiniMax-H3-20260901"


async def test_query_task_cancelled_maps_to_failed(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "cancelled"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )
    assert result["status"] == "failed"


async def test_query_task_expired_maps_to_failed(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "expired"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )
    assert result["status"] == "failed"


async def test_query_task_non_terminal_maps_to_running(adapter):
    for s in ["queued", "processing", "pending"]:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=_mock_response(200, {"task": {"id": "x", "status": s}})
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.algorithm.clients.minimax_video.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.query_task(
                api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
            )
        assert result["status"] == "running", f"status {s} should map to running"


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
                model="MiniMax-H3",
                prompt="x",
                resolution="2K",
                duration=5,
                ratio="16:9",
            )
    assert "sensitive content" in str(exc.value)


async def test_create_task_html_502_raises_minimax_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=_mock_bad_json_response(502))
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
                model="MiniMax-H3",
                prompt="x",
                resolution="2K",
                duration=5,
                ratio="16:9",
            )
    assert "502" in str(exc.value)


async def test_query_task_html_504_raises_minimax_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_bad_json_response(504))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(MinimaxVideoError) as exc:
            await adapter.query_task(
                api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
            )
    assert "504" in str(exc.value)


async def test_query_task_dict_error_coerced_to_string(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "task": {
                    "id": "x",
                    "status": "failed",
                    "error": {"code": 1026, "message": "sensitive content"},
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
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )

    assert result["status"] == "failed"
    assert isinstance(result["error"], str)
    assert "sensitive content" in result["error"]


def _mock_bad_json_response(status_code: int):
    import json as _json
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(side_effect=_json.JSONDecodeError("Expecting value", "", 0))
    return resp


async def test_create_task_html_502_raises_minimax_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=_mock_bad_json_response(502))
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
                model="MiniMax-H3",
                prompt="x",
                resolution="2K",
                duration=5,
                ratio="16:9",
            )
    assert "502" in str(exc.value)


async def test_query_task_html_504_raises_minimax_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_bad_json_response(504))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(MinimaxVideoError) as exc:
            await adapter.query_task(
                api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
            )
    assert "504" in str(exc.value)


async def test_query_task_dict_error_coerced_to_string(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "task": {
                    "id": "x",
                    "status": "failed",
                    "error": {"code": 1026, "message": "sensitive content"},
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
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )

    assert result["status"] == "failed"
    assert isinstance(result["error"], str)
    assert "sensitive content" in result["error"]
