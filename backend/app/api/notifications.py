from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user, require_admin
from app.database import get_db
from app.utils import utc_iso
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class CreateNotificationInput(BaseModel):
    user_id: int
    title: str
    content: str
    type: str = "system"


class BatchNotificationInput(BaseModel):
    title: str
    content: str
    type: str = "system"
    user_ids: Optional[list[int]] = None


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "title": row["title"],
        "content": row["content"],
        "type": row["type"],
        "isRead": bool(row["is_read"]),
        "isRecalled": bool(row["is_recalled"]),
        "createdAt": utc_iso(row["created_at"]),
    }


# ─── 用户端 ───────────────────────────────────────────────

@router.get("")
def list_notifications(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
):
    db = get_db()
    where = "user_id = ? AND is_recalled = 0"
    params = [user["id"]]
    if unread_only:
        where += " AND is_read = 0"

    total = db.execute(f"SELECT COUNT(*) FROM notifications WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()
    db.close()

    return {
        "data": [_row_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "message": "success",
        "code": 200,
    }


@router.get("/unread-count")
def get_unread_count(user: dict = Depends(get_current_user)):
    db = get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0 AND is_recalled = 0",
        (user["id"],),
    ).fetchone()[0]
    db.close()
    return {"data": {"count": count}, "message": "success", "code": 200}


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ? AND is_recalled = 0",
        (notification_id, user["id"]),
    )
    db.commit()
    db.close()
    return {"message": "marked as read", "code": 200}


@router.put("/read-all")
def mark_all_as_read(user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0 AND is_recalled = 0",
        (user["id"],),
    )
    db.commit()
    db.close()
    return {"message": "all marked as read", "code": 200}


@router.delete("/clear-all")
def clear_all_notifications(user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id = ? AND is_recalled = 0", (user["id"],))
    db.commit()
    db.close()
    return {"message": "cleared", "code": 200}


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT id FROM notifications WHERE id = ? AND user_id = ? AND is_recalled = 0",
        (notification_id, user["id"]),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Notification not found")
    db.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
    db.commit()
    db.close()
    return {"message": "deleted", "code": 200}


# ─── 管理员端 ─────────────────────────────────────────────

@router.post("")
def create_notification(body: CreateNotificationInput, user: dict = Depends(require_admin)):
    db = get_db()
    target = db.execute("SELECT id FROM users WHERE id = ?", (body.user_id,)).fetchone()
    if not target:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")

    cursor = db.execute(
        "INSERT INTO notifications (user_id, title, content, type) VALUES (?, ?, ?, ?) RETURNING id",
        (body.user_id, body.title, body.content, body.type),
    )
    db.commit()
    result_id = cursor.fetchone()["id"]
    db.close()
    return {"data": {"id": result_id}, "message": "sent", "code": 200}


@router.post("/batch")
def batch_send_notification(body: BatchNotificationInput, user: dict = Depends(require_admin)):
    db = get_db()
    if body.user_ids:
        placeholders = ",".join("?" for _ in body.user_ids)
        rows = db.execute(f"SELECT id FROM users WHERE id IN ({placeholders})", body.user_ids).fetchall()
        user_ids = [r["id"] for r in rows]
    else:
        rows = db.execute("SELECT id FROM users").fetchall()
        user_ids = [r["id"] for r in rows]

    if not user_ids:
        db.close()
        raise HTTPException(status_code=400, detail="No valid users")

    count = 0
    for uid in user_ids:
        db.execute(
            "INSERT INTO notifications (user_id, title, content, type) VALUES (?, ?, ?, ?)",
            (uid, body.title, body.content, body.type),
        )
        count += 1
    db.commit()
    db.close()
    return {"data": {"count": count}, "message": f"Sent to {count} users", "code": 200}


@router.get("/sent")
def list_sent_notifications(
    user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """管理员查看已发送的通知列表"""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM notifications WHERE is_recalled = 0").fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        "SELECT * FROM notifications WHERE is_recalled = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()
    db.close()
    return {
        "data": [_row_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "message": "success",
        "code": 200,
    }


@router.put("/{notification_id}/recall")
def recall_notification(notification_id: int, user: dict = Depends(require_admin)):
    """管理员撤销已发送的通知（软删除）"""
    db = get_db()
    row = db.execute("SELECT id FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Notification not found")
    db.execute("UPDATE notifications SET is_recalled = 1 WHERE id = ?", (notification_id,))
    db.commit()
    db.close()
    return {"message": "recalled", "code": 200}
