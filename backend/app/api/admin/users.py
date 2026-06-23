"""
Admin user management — raw psycopg2 (SQLModel removed).
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, SuperUserDep
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin-users"])


class UpdateUserInput(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    email: str | None = None


class SendNotificationInput(BaseModel):
    user_id: int
    title: str
    content: str
    type: str = "system"


@router.get("")
def list_users(db: SessionDep, _admin: SuperUserDep):
    """List all users with usage statistics (admin only)."""
    rows = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    users = [User(**r) for r in rows]

    # Per-user aggregate stats via raw SQL
    stats_rows = db.execute(
        """
        SELECT
            t.user_id,
            COUNT(*)                                        AS total_tasks,
            COUNT(*) FILTER (WHERE t.status = 'completed')  AS completed_tasks,
            COUNT(*) FILTER (WHERE t.status = 'failed')     AS failed_tasks,
            COUNT(DISTINCT s.id)                            AS total_solutions,
            MAX(t.updated_at)                               AS last_active
        FROM tasks t
        LEFT JOIN solutions s ON s.task_id = t.id
        GROUP BY t.user_id
        """
    ).fetchall()
    stats_map: dict[int, dict] = {}
    for r in stats_rows:
        stats_map[r["user_id"]] = {
            "totalTasks": r["total_tasks"],
            "completedTasks": r["completed_tasks"],
            "failedTasks": r["failed_tasks"],
            "totalSolutions": r["total_solutions"],
            "lastActive": r["last_active"] or "",
        }

    return {
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email or "",
                "role": u.role,
                "isActive": bool(u.is_active),
                "createdAt": u.created_at or "",
                "stats": stats_map.get(
                    u.id or 0,
                    {
                        "totalTasks": 0,
                        "completedTasks": 0,
                        "failedTasks": 0,
                        "totalSolutions": 0,
                        "lastActive": "",
                    },
                ),
            }
            for u in users
        ],
        "message": "success",
        "code": 200,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserInput,
    db: SessionDep,
    _admin: SuperUserDep,
):
    """Update user's is_active or role (admin only)."""
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    user = User(**row)

    updates = []
    params: list[int | str] = []
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if body.is_active else 0)
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")
        updates.append("role = ?")
        params.append(body.role)
    if body.email is not None:
        updates.append("email = ?")
        params.append(body.email)

    if updates:
        params.append(user_id)
        db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        db.commit()

    # Re-fetch updated user
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    user = User(**row)

    return {
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email or "",
            "role": user.role,
            "isActive": bool(user.is_active),
            "createdAt": user.created_at or "",
        },
        "message": "success",
        "code": 200,
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: SessionDep,
    current_user: CurrentUser,
    _admin: SuperUserDep,
):
    """Delete user and related records (admin only, cannot delete self)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")

    logger.info("Deleting user %s and related records", user_id)

    # Delete related records
    _sql_deps: list[str] = [
        "DELETE FROM analyses WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)",
        "DELETE FROM workflows WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)",
        "DELETE FROM solutions WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)",
        "DELETE FROM tasks WHERE user_id = ?",
        "DELETE FROM evaluations WHERE user_id = ?",
        "DELETE FROM feedbacks WHERE user_id = ?",
        "DELETE FROM audit_log WHERE user_id = ?",
        "DELETE FROM notifications WHERE user_id = ?",
    ]
    for sql in _sql_deps:
        db.execute(sql, (user_id,))

    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()

    return {"data": None, "message": "已删除", "code": 200}
