"""后台视频轮询器测试 — 多供应商分组轮询。

mock 服务 + 真实 adapter 的 query_task，验证单轮状态推进、孤儿回收、按 provider 分组。
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.algorithm.clients.video_base import VideoRegistry
from app.services import video_poller as vp_mod
from app.services.video_poller import VideoPoller


MINIMAX_ROW = {"protocol": "video_minimax", "api_host": "https://api.minimaxi.com"}
BAILIAN_ROW = {"protocol": "video_dashscope", "api_host": "https://dashscope.aliyuncs.com/api/v1"}


def test_poll_once_advances_succeeded_task():
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"},
        {"id": "t2", "remoteTaskId": "r2", "providerId": "minimax"},
    ]
    query_results = {
        "r1": {"status": "succeeded", "video_url": "https://x/1.mp4", "error": None},
        "r2": {"status": "running", "video_url": None, "error": None},
    }
    minimax_adapter = VideoRegistry.get("video_minimax")

    with patch.object(
        vp_mod.video_task_service, "list_active", return_value=active
    ), patch.object(vp_mod, "_lease_key", return_value="sk"), patch.object(
        vp_mod, "_read_provider_row", return_value=MINIMAX_ROW
    ), patch.object(
        minimax_adapter,
        "query_task",
        new=AsyncMock(side_effect=lambda **kw: query_results[kw["remote_task_id"]]),
    ), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        advanced = _run(poller.poll_once())

    applied_ids = {c.args[0] for c in mock_apply.call_args_list}
    assert "t1" in applied_ids
    assert "t2" in applied_ids
    assert advanced == 2


def test_poll_once_groups_by_provider_id():
    """两个不同 provider 的任务应分别 lease 各自的 key 并调用各自 adapter。"""
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"},
        {"id": "t2", "remoteTaskId": "r2", "providerId": "bailian"},
    ]
    minimax_adapter = VideoRegistry.get("video_minimax")
    dashscope_adapter = VideoRegistry.get("video_dashscope")

    def mock_lease(provider_id):
        return {"minimax": "sk-mm", "bailian": "sk-bl"}.get(provider_id)

    def mock_read(provider_id):
        return {"minimax": MINIMAX_ROW, "bailian": BAILIAN_ROW}.get(provider_id)

    with patch.object(vp_mod, "_lease_key", side_effect=mock_lease), \
         patch.object(vp_mod, "_read_provider_row", side_effect=mock_read), \
         patch.object(vp_mod.video_task_service, "list_active", return_value=active), \
         patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply, \
         patch.object(
             minimax_adapter,
             "query_task",
             new=AsyncMock(return_value={"status": "succeeded", "video_url": "x", "error": None}),
         ), \
         patch.object(
             dashscope_adapter,
             "query_task",
             new=AsyncMock(return_value={"status": "running", "video_url": None, "error": None}),
         ):
        _run(poller.poll_once())

    assert mock_apply.call_count == 2


def test_poll_once_skips_group_without_key():
    """某 provider 无密钥时只跳过该组，不影响其他组。"""
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"},
        {"id": "t2", "remoteTaskId": "r2", "providerId": "no-key-provider"},
    ]
    minimax_adapter = VideoRegistry.get("video_minimax")

    def mock_lease(provider_id):
        return "sk" if provider_id == "minimax" else None

    with patch.object(vp_mod, "_lease_key", side_effect=mock_lease), \
         patch.object(vp_mod, "_read_provider_row", return_value=MINIMAX_ROW), \
         patch.object(vp_mod.video_task_service, "list_active", return_value=active), \
         patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply, \
         patch.object(
             minimax_adapter,
             "query_task",
             new=AsyncMock(return_value={"status": "succeeded", "video_url": "x", "error": None}),
         ):
        _run(poller.poll_once())

    # 只有 minimax 组的任务被回写
    assert mock_apply.call_count == 1


def test_poll_once_no_key_skips():
    poller = VideoPoller(interval_seconds=5)
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"}],
    ), patch.object(vp_mod, "_lease_key", return_value=None), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        _run(poller.poll_once())
    mock_apply.assert_not_called()


def test_poll_once_query_error_does_not_crash():
    poller = VideoPoller(interval_seconds=5)
    minimax_adapter = VideoRegistry.get("video_minimax")
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"}],
    ), patch.object(vp_mod, "_lease_key", return_value="sk"), patch.object(
        vp_mod, "_read_provider_row", return_value=MINIMAX_ROW
    ), patch.object(
        minimax_adapter, "query_task", new=AsyncMock(side_effect=RuntimeError("boom"))
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
        vp_mod, "_lease_key", return_value="sk"
    ), patch.object(
        vp_mod, "_read_provider_row", return_value=MINIMAX_ROW
    ):
        count = _run(poller.poll_once())

    mock_fail.assert_called_once()
    assert mock_fail.call_args.args[0] == "orphan"
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
        vp_mod, "_lease_key", return_value="sk"
    ):
        count = _run(poller.poll_once())

    mock_fail.assert_not_called()
    assert count == 0


def _run(coro):
    import asyncio

    return asyncio.run(coro)
