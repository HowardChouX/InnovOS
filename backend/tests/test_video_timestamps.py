"""时间戳回归测试 — utc_iso 与 _row_to_dict 必须能处理 TIMESTAMPTZ datetime。

video_tasks 是首个 TIMESTAMPTZ 列经 RealDictCursor 返回 datetime 对象的表，
旧版 utc_iso 对 datetime 做字符串 `in` 运算会抛 TypeError，导致所有视频读路径 500。
"""
from datetime import datetime, timezone

from app.services.video_task_service import _row_to_dict
from app.utils import utc_iso


def test_utc_iso_handles_tz_aware_datetime():
    dt = datetime(2026, 8, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert utc_iso(dt) == "2026-08-02T10:00:00+00:00"


def test_utc_iso_handles_naive_datetime():
    dt = datetime(2026, 8, 2, 10, 0, 0)
    # naive datetime 无偏移，isoformat() 不带后缀（不崩溃即可）
    assert utc_iso(dt) == "2026-08-02T10:00:00"


def test_utc_iso_string_behavior_unchanged():
    assert utc_iso(None) is None
    assert utc_iso("2026-08-02 10:00:00") == "2026-08-02 10:00:00+00:00"
    assert utc_iso("2026-08-02T10:00:00+00:00") == "2026-08-02T10:00:00+00:00"
    assert utc_iso("2026-08-02T10:00:00Z") == "2026-08-02T10:00:00Z"


def test_row_to_dict_with_datetime_timestamps():
    # RealDictCursor 对 TIMESTAMPTZ 返回 datetime；旧实现此处抛 TypeError
    row = {
        "id": "abc",
        "user_id": 1,
        "provider_id": "minimax",
        "model": "MiniMax-H3",
        "prompt": "p",
        "resolution": "768P",
        "duration": 5,
        "ratio": "16:9",
        "remote_task_id": None,
        "status": "pending",
        "video_url": None,
        "error": None,
        "created_at": datetime(2026, 8, 2, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 8, 2, 10, 0, 0, tzinfo=timezone.utc),
    }
    result = _row_to_dict(row)
    assert result["createdAt"] == "2026-08-02T10:00:00+00:00"
    assert result["updatedAt"] == "2026-08-02T10:00:00+00:00"
    assert result["status"] == "pending"
