"""/api/video 路由测试 — TestClient + 依赖覆盖 + mock 服务/适配器。"""
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


def test_generate_creates_task_and_returns_id(client):
    created = {"id": "task-1", "status": "pending"}
    with patch.object(
        video_api.video_task_service, "create", return_value=created
    ) as mock_create, patch.object(
        video_api.video_task_service, "set_remote_task"
    ) as mock_set, patch.object(
        video_api, "_lease_minimax_key", return_value=("sk-test", "https://api.minimaxi.com")
    ), patch.object(
        video_api.minimax_video_adapter,
        "create_task",
        new=AsyncMock(return_value="remote-123"),
    ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "一只猫", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["taskId"] == "task-1"
    mock_create.assert_called_once()
    mock_set.assert_called_once_with("task-1", "remote-123")


def test_generate_rejects_invalid_duration(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "x", "resolution": "768P", "duration": 99, "ratio": "16:9"},
    )
    assert resp.status_code == 422


def test_generate_rejects_invalid_ratio(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "x", "resolution": "768P", "duration": 5, "ratio": "adaptive"},
    )
    assert resp.status_code == 422


def test_generate_rejects_empty_prompt(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "   ", "resolution": "768P", "duration": 5, "ratio": "16:9"},
    )
    assert resp.status_code == 422


def test_generate_no_key_returns_error(client):
    with patch.object(video_api, "_lease_minimax_key", return_value=(None, None)):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "x", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
    assert "MiniMax" in resp.json()["detail"]


def test_generate_unexpected_error_marks_failed(client):
    """远端创建后发生非 MinimaxVideoError 异常 → 标记 failed 并返回 500，不留孤儿。"""
    created = {"id": "task-1", "status": "pending"}
    with patch.object(
        video_api.video_task_service, "create", return_value=created
    ), patch.object(
        video_api, "_lease_minimax_key", return_value=("sk-test", "https://api.minimaxi.com")
    ), patch.object(
        video_api.minimax_video_adapter,
        "create_task",
        new=AsyncMock(return_value="remote-123"),
    ), patch.object(
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
    # 任务存在但 user_id 不匹配
    with patch.object(
        video_api.video_task_service, "get", return_value={"id": "t1", "userId": 999}
    ):
        resp = client.get("/api/video/tasks/t1")
    assert resp.status_code == 404


def test_delete_task(client):
    with patch.object(video_api.video_task_service, "delete", return_value=True):
        resp = client.delete("/api/video/tasks/t1")
    assert resp.status_code == 200
