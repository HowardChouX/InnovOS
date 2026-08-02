"""视频任务仓储服务测试 — 用可控 fake db_session。"""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.services import video_task_service as vts_mod
from app.services.video_task_service import VideoTaskService


class FakeCursor:
    def __init__(self, fetchone_val=None, fetchall_val=None):
        self._fetchone = fetchone_val
        self._fetchall = fetchall_val or []

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


@pytest.fixture
def fake_db(monkeypatch):
    """patch 服务模块内的 db_session，返回 (db_mock, 捕获的 SQL 列表)。"""
    db = MagicMock()
    captured: list[tuple[str, object]] = []

    def _execute(sql, params=None):
        captured.append((sql, params))
        return db._cursor if hasattr(db, "_cursor") else FakeCursor()

    db.execute = _execute
    db._cursor = FakeCursor()

    @contextmanager
    def _session():
        yield db

    monkeypatch.setattr(vts_mod, "db_session", _session)
    return db, captured


def test_create_inserts_pending_task_and_returns_dict(fake_db):
    db, captured = fake_db
    # INSERT ... RETURNING id 后服务会 SELECT 回读；给 SELECT 一个行
    row = {
        "id": "abc", "user_id": 1, "provider_id": "minimax", "model": "MiniMax-H3",
        "prompt": "p", "resolution": "768P", "duration": 5, "ratio": "16:9",
        "remote_task_id": None, "status": "pending", "video_url": None,
        "error": None, "created_at": "2026-08-02 10:00:00", "updated_at": "2026-08-02 10:00:00",
    }
    db._cursor = FakeCursor(fetchone_val=row)

    svc = VideoTaskService()
    result = svc.create(1, prompt="p", resolution="768P", duration=5, ratio="16:9")

    assert result["status"] == "pending"
    assert result["userId"] == 1
    # 第一条 SQL 是 INSERT
    insert_sql, insert_params = captured[0]
    assert "INSERT INTO video_tasks" in insert_sql
    assert "p" in insert_params  # prompt 在参数里


def test_list_by_user_filters_by_user(fake_db):
    db, captured = fake_db
    db._cursor = FakeCursor(fetchall_val=[])

    svc = VideoTaskService()
    svc.list_by_user(7)

    sql, params = captured[0]
    assert "FROM video_tasks" in sql
    assert "user_id" in sql
    assert 7 in params


def test_list_active_selects_nonterminal_statuses(fake_db):
    db, captured = fake_db
    db._cursor = FakeCursor(fetchall_val=[])

    svc = VideoTaskService()
    svc.list_active()

    sql, _ = captured[0]
    assert "status" in sql
    for s in ("pending", "queued", "running"):
        assert s in sql


def test_apply_remote_status_updates_url(fake_db):
    db, captured = fake_db
    svc = VideoTaskService()
    svc.apply_remote_status(
        "abc", status="succeeded", video_url="https://x/y.mp4", error=None
    )

    sql, params = captured[0]
    assert "UPDATE video_tasks" in sql
    assert "succeeded" in params
    assert "https://x/y.mp4" in params
