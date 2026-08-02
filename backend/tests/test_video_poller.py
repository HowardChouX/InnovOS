"""后台视频轮询器测试 — mock 服务 + 适配器，验证单轮状态推进。"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services import video_poller as vp_mod
from app.services.video_poller import VideoPoller


def test_poll_once_advances_succeeded_task():
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1"},
        {"id": "t2", "remoteTaskId": "r2"},
    ]
    query_results = {
        "r1": {"status": "succeeded", "video_url": "https://x/1.mp4", "error": None},
        "r2": {"status": "running", "video_url": None, "error": None},
    }

    with patch.object(
        vp_mod.video_task_service, "list_active", return_value=active
    ), patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ), patch.object(
        vp_mod.minimax_video_adapter,
        "query_task",
        new=AsyncMock(side_effect=lambda *, api_key, api_host, remote_task_id: query_results[remote_task_id]),
    ), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        advanced = _run(poller.poll_once())

    # 只有 succeeded 的 t1 被回写终态；running 的 t2 也回写（状态同步）
    applied_ids = {c.args[0] for c in mock_apply.call_args_list}
    assert "t1" in applied_ids
    assert "t2" in applied_ids


def test_poll_once_no_key_skips():
    poller = VideoPoller(interval_seconds=5)
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1"}],
    ), patch.object(vp_mod, "_lease_minimax_key", return_value=(None, None)), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        _run(poller.poll_once())
    mock_apply.assert_not_called()


def test_poll_once_query_error_does_not_crash():
    poller = VideoPoller(interval_seconds=5)
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1"}],
    ), patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ), patch.object(
        vp_mod.minimax_video_adapter,
        "query_task",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ), patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply:
        # 不应抛出
        _run(poller.poll_once())
    mock_apply.assert_not_called()


def test_poll_once_marks_stale_pending_failed():
    """无 remoteTaskId 且 createdAt 过旧的 pending 任务 → 标记 failed（孤儿回收）。"""
    poller = VideoPoller(interval_seconds=5)
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    active = [{"id": "orphan", "remoteTaskId": None, "createdAt": old}]

    with patch.object(
        vp_mod.video_task_service, "list_active", return_value=active
    ), patch.object(
        vp_mod.video_task_service, "mark_failed"
    ) as mock_fail, patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ), patch.object(
        vp_mod.minimax_video_adapter, "query_task", new=AsyncMock()
    ) as mock_query:
        count = _run(poller.poll_once())

    mock_fail.assert_called_once()
    assert mock_fail.call_args.args[0] == "orphan"
    mock_query.assert_not_called()  # 无 remote id，不查询远端
    assert count == 1


def test_poll_once_keeps_fresh_pending():
    """无 remoteTaskId 但 createdAt 很新的 pending 任务 → 保留，不标记失败。"""
    poller = VideoPoller(interval_seconds=5)
    fresh = datetime.now(timezone.utc).isoformat()
    active = [{"id": "fresh", "remoteTaskId": None, "createdAt": fresh}]

    with patch.object(
        vp_mod.video_task_service, "list_active", return_value=active
    ), patch.object(
        vp_mod.video_task_service, "mark_failed"
    ) as mock_fail, patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ):
        count = _run(poller.poll_once())

    mock_fail.assert_not_called()
    assert count == 0


def _run(coro):
    import asyncio

    return asyncio.run(coro)
