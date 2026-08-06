"""/api/video 路由测试 — 门控 + 注册表 + options。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import video as video_api
from app.auth import get_current_user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(video_api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test"}
    with TestClient(app) as c:
        yield c


MINIMAX_PROVIDER = {
    "provider_id": "minimax",
    "protocol": "video_minimax",
    "api_host": "https://api.minimaxi.com",
    "api_model": "MiniMax-H3",
}


# ── options ──

def test_options_returns_403_when_no_video_provider(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=None):
        resp = client.get("/api/video/options")
    assert resp.status_code == 403


def test_options_returns_capabilities(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.get("/api/video/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["providerId"] == "minimax"
    assert data["protocol"] == "video_minimax"
    assert data["model"] == "MiniMax-H3"
    assert "capabilities" in data


# ── generate ──

def test_generate_403_when_no_video_provider(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=None):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 403


def test_generate_400_when_non_video_protocol(client):
    """已开通但协议不是 video_* → 400。"""
    with patch.object(video_api, "_select_user_video_provider", return_value={
        "provider_id": "deepseek", "protocol": "openai",
        "api_host": "https://api.deepseek.com", "api_model": "deepseek-chat",
    }):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
    assert "不是视频模型服务" in resp.json()["detail"]


def test_generate_rejects_invalid_resolution(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "4K", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 422


def test_generate_rejects_invalid_duration(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 99, "ratio": "16:9"},
        )
    assert resp.status_code == 422


def test_generate_rejects_invalid_ratio(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "adaptive"},
        )
    assert resp.status_code == 422


def test_generate_rejects_empty_prompt(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "   ", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 422


def test_generate_minimax_path(client):
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "set_remote_task") as mock_set, \
         patch.object(video_api.video_task_service, "mark_failed"), \
         patch.object(
             video_api.VideoRegistry.get("video_minimax"),
             "create_task",
             new=AsyncMock(return_value="remote-123"),
         ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["taskId"] == "task-1"
        # create 应透传 provider_id 与 model
        _, kwargs = video_api.video_task_service.create.call_args
        assert kwargs["provider_id"] == "minimax"
        assert kwargs["model"] == "MiniMax-H3"
        mock_set.assert_called_once_with("task-1", "remote-123")


def test_generate_no_key_returns_error(client):
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value=None), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "mark_failed") as mock_fail:
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
    assert "未配置密钥" in resp.json()["detail"]
    mock_fail.assert_called_once()


def test_generate_adapter_error_returns_400(client):
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "mark_failed") as mock_fail, \
         patch.object(
             video_api.VideoRegistry.get("video_minimax"),
             "create_task",
             new=AsyncMock(side_effect=video_api.VideoAdapterError("sensitive content")),
         ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "bad", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
    assert "sensitive content" in resp.json()["detail"]
    mock_fail.assert_called_once()


def test_generate_unexpected_error_marks_failed(client):
    """远端创建后发生非 VideoAdapterError 异常 → 标记 failed 并返回 500，不留孤儿。"""
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=MINIMAX_PROVIDER), \
         patch.object(video_api, "_lease_key", return_value="sk-test"), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(
             video_api.VideoRegistry.get("video_minimax"),
             "create_task",
             new=AsyncMock(return_value="remote-123"),
         ), \
         patch.object(
             video_api.video_task_service,
             "set_remote_task",
             side_effect=RuntimeError("db down"),
         ), patch.object(
             video_api.video_task_service, "mark_failed"
         ) as mock_fail:
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "一只猫", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )

    assert resp.status_code == 500
    mock_fail.assert_called_once()
    assert mock_fail.call_args.args[0] == "task-1"


def test_generate_dashscope_path(client):
    """DashScope 供应商走 video_dashscope adapter。"""
    provider = {
        "provider_id": "bailian",
        "protocol": "video_dashscope",
        "api_host": "https://dashscope.aliyuncs.com/api/v1",
        "api_model": "wan2.7-t2v-2026-06-12",
    }
    created = {"id": "task-2", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=provider), \
         patch.object(video_api, "_lease_key", return_value="sk-ds"), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "set_remote_task") as mock_set, \
         patch.object(video_api.video_task_service, "mark_failed"), \
         patch.object(
             video_api.VideoRegistry.get("video_dashscope"),
             "create_task",
             new=AsyncMock(return_value="tsk-456"),
         ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "1080P", "duration": 15, "ratio": "16:9"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["taskId"] == "task-2"
    mock_set.assert_called_once_with("task-2", "tsk-456")


# ── tasks 端点（保持不变）──

def test_list_tasks_returns_user_tasks(client):
    with patch.object(
        video_api.video_task_service,
        "list_by_user",
        return_value=[{"id": "t1", "status": "succeeded"}],
    ):
        resp = client.get("/api/video/tasks")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["id"] == "t1"


def test_get_task_foreign_returns_404(client):
    with patch.object(
        video_api.video_task_service, "get", return_value={"id": "t1", "userId": 999}
    ):
        resp = client.get("/api/video/tasks/t1")
    assert resp.status_code == 404


def test_delete_task(client):
    with patch.object(video_api.video_task_service, "delete", return_value=True):
        resp = client.delete("/api/video/tasks/t1")
    assert resp.status_code == 200
