"""视频生成任务仓储 — video_tasks 表的唯一 SQL 入口。

API 层与后台轮询器共用本服务，避免 SQL 重复。所有 DB 操作走 db_session。
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.database import db_session
from app.utils import utc_iso

ACTIVE_STATUSES = ("pending", "queued", "running")


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row) if not isinstance(row, dict) else row
    return {
        "id": d.get("id"),
        "userId": d.get("user_id"),
        "providerId": d.get("provider_id"),
        "model": d.get("model"),
        "prompt": d.get("prompt"),
        "resolution": d.get("resolution"),
        "duration": d.get("duration"),
        "ratio": d.get("ratio"),
        "remoteTaskId": d.get("remote_task_id"),
        "status": d.get("status"),
        "videoUrl": d.get("video_url"),
        "error": d.get("error"),
        "createdAt": utc_iso(d.get("created_at")),
        "updatedAt": utc_iso(d.get("updated_at")),
    }


class VideoTaskService:
    def create(
        self,
        user_id: int,
        *,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
        provider_id: str = "minimax",
        model: str = "MiniMax-H3",
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        with db_session() as db:
            db.execute(
                "INSERT INTO video_tasks "
                "(id, user_id, prompt, resolution, duration, ratio, provider_id, model, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (task_id, user_id, prompt, resolution, duration, ratio,
                 provider_id, model),
            )
            row = db.execute(
                "SELECT * FROM video_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_dict(row)

    def set_remote_task(self, task_id: str, remote_task_id: str) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET remote_task_id = ?, status = 'queued', "
                "updated_at = now() WHERE id = ?",
                (remote_task_id, task_id),
            )

    def mark_failed(self, task_id: str, error: str) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET status = 'failed', error = ?, "
                "updated_at = now() WHERE id = ?",
                (error, task_id),
            )

    def get(self, task_id: str) -> Optional[dict[str, Any]]:
        with db_session() as db:
            row = db.execute(
                "SELECT * FROM video_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_by_user(self, user_id: int) -> list[dict[str, Any]]:
        with db_session() as db:
            rows = db.execute(
                "SELECT * FROM video_tasks WHERE user_id = ? "
                "ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def delete(self, task_id: str, user_id: int) -> bool:
        with db_session() as db:
            cur = db.execute(
                "DELETE FROM video_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            return (cur.rowcount or 0) > 0

    def list_active(self) -> list[dict[str, Any]]:
        # ACTIVE_STATUSES 为硬编码常量，直接内联（测试断言 SQL 文本含状态字面量）
        in_clause = ",".join(f"'{s}'" for s in ACTIVE_STATUSES)
        with db_session() as db:
            rows = db.execute(
                f"SELECT * FROM video_tasks WHERE status IN ({in_clause})"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def apply_remote_status(
        self,
        task_id: str,
        *,
        status: str,
        video_url: Optional[str],
        error: Optional[str],
    ) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET status = ?, video_url = ?, error = ?, "
                "updated_at = now() WHERE id = ?",
                (status, video_url, error, task_id),
            )


video_task_service = VideoTaskService()
