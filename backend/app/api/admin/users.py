"""
Admin user management — SQLModel-based.

Migrated from raw psycopg2 to SQLModel ORM + deps.CurrentUser.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select, text

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
def list_users(session: SessionDep, _admin: SuperUserDep):
    """List all users with usage statistics (admin only)."""
    users = session.exec(select(User).order_by(User.created_at.desc())).all()  # type: ignore[union-attr]

    # Per-user aggregate stats via raw SQL
    rows = session.execute(
        text("""
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
        """)
    ).fetchall()
    stats_map: dict[int, dict] = {}
    for r in rows:
        stats_map[r[0]] = {
            "totalTasks": r[1],
            "completedTasks": r[2],
            "failedTasks": r[3],
            "totalSolutions": r[4],
            "lastActive": r[5] or "",
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
    session: SessionDep,
    _admin: SuperUserDep,
):
    """Update user's is_active or role (admin only)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.is_active is not None:
        user.is_active = 1 if body.is_active else 0
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")
        user.role = body.role
    if body.email is not None:
        user.email = body.email

    session.add(user)
    session.commit()
    session.refresh(user)

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
    session: SessionDep,
    current_user: CurrentUser,
    _admin: SuperUserDep,
):
    """Delete user and related records (admin only, cannot delete self)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    logger.info("Deleting user %s and related records", user_id)

    # Delete related records via raw SQL (tables without SQLModel ORM)
    _sql_deps: list[str] = [
        "DELETE FROM analyses WHERE task_id IN (SELECT id FROM tasks WHERE user_id = :uid)",
        "DELETE FROM workflows WHERE task_id IN (SELECT id FROM tasks WHERE user_id = :uid)",
        "DELETE FROM solutions WHERE task_id IN (SELECT id FROM tasks WHERE user_id = :uid)",
        "DELETE FROM tasks WHERE user_id = :uid",
        "DELETE FROM evaluations WHERE user_id = :uid",
        "DELETE FROM feedbacks WHERE user_id = :uid",
        "DELETE FROM audit_log WHERE user_id = :uid",
        "DELETE FROM notifications WHERE user_id = :uid",
    ]
    for sql in _sql_deps:
        session.execute(text(sql), {"uid": user_id})

    session.delete(user)
    session.commit()

    return {"data": None, "message": "已删除", "code": 200}
