import json
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user
from app.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskInput(BaseModel):
    title: str
    description: str
    tags: list[str] = []


class UpdateTaskInput(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


STATUSES = {"pending", "analyzing", "completed", "failed"}


def row_to_dict(row):
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "tags": json.loads(row["tags"]),
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


@router.get("")
def list_tasks(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=200),
    status: str = Query(""),
):
    db = get_db()
    params: list = [user["id"]]
    where = "user_id = ?"

    if search:
        where += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status and status in STATUSES:
        where += " AND status = ?"
        params.append(status)

    total = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM tasks WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()
    db.close()
    return {
        "data": [row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": max(1, (total + page_size - 1) // page_size),
        "message": "success",
        "code": 200,
    }


@router.post("")
def create_task(body: CreateTaskInput, user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (user_id, title, description, tags) VALUES (?, ?, ?, ?)",
        (user["id"], body.title, body.description, json.dumps(body.tags)),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    db.close()
    return {"data": row_to_dict(row), "message": "success", "code": 200}


@router.get("/{task_id}")
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, user["id"]),
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"data": row_to_dict(row), "message": "success", "code": 200}


@router.put("/{task_id}")
def update_task(task_id: int, body: UpdateTaskInput, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, user["id"]),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    updates = []
    params: list = []
    if body.title is not None:
        updates.append("title = ?")
        params.append(body.title)
    if body.description is not None:
        updates.append("description = ?")
        params.append(body.description)
    if body.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(body.tags))
    if body.status is not None:
        if body.status not in STATUSES:
            db.close()
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
        updates.append("status = ?")
        params.append(body.status)

    if updates:
        updates.append("updated_at = datetime('now')")
        params.extend([task_id, user["id"]])
        db.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params,
        )
        db.commit()

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    db.close()
    return {"data": row_to_dict(row), "message": "success", "code": 200}


@router.delete("/{task_id}")
def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"]))
    db.commit()
    db.close()
    return {"data": None, "message": "deleted", "code": 200}
