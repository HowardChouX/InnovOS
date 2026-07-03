import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.audit import log_audit
from app.auth import get_current_user
from app.database import db_session
from app.utils import utc_iso

ALLOWED_TASK_FIELDS = {"title", "description", "tags", "status", "updated_at"}


def _validate_columns(fields: list[str], allowed: set[str]) -> None:
    for f in fields:
        if f not in allowed:
            raise ValueError(f"Invalid column: {f}")


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskInput(BaseModel):
    title: str
    description: str
    tags: list[str] = []


class UpdateTaskInput(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: str | None = None


STATUSES = {"pending", "analyzing", "completed", "failed"}


def row_to_dict(row):
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "tags": json.loads(row["tags"]),
        "status": row["status"],
        "createdAt": utc_iso(row["created_at"]),
        "updatedAt": utc_iso(row["updated_at"]),
    }


@router.get("")
def list_tasks(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=200),
    status: str = Query(""),
):
    with db_session() as db:
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
    with db_session() as db:
        cursor = db.execute(
            "INSERT INTO tasks (user_id, title, description, tags) VALUES (?, ?, ?, ?) RETURNING id",
            (user["id"], body.title, body.description, json.dumps(body.tags)),
        )
        inserted_id = cursor.fetchone()["id"]
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (inserted_id,)).fetchone()

        return {"data": row_to_dict(row), "message": "success", "code": 200}


@router.put("/{task_id}")
def update_task(
    task_id: str,
    body: UpdateTaskInput,
    user: dict = Depends(get_current_user),
):
    with db_session() as db:
        task = db.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        update_fields = []
        update_vals = []
        if body.title is not None:
            update_fields.append("title = ?")
            update_vals.append(body.title)
        if body.description is not None:
            update_fields.append("description = ?")
            update_vals.append(body.description)
        if body.tags is not None:
            update_fields.append("tags = ?")
            update_vals.append(json.dumps(body.tags))
        if body.status is not None:
            if body.status not in STATUSES:
                raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
            update_fields.append("status = ?")
            update_vals.append(body.status)

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_fields.append("updated_at = NOW()")
        update_vals.extend([task_id, user["id"]])

        db.execute(
            f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?",
            update_vals,
        )

        updated_task = db.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user["id"]),
        ).fetchone()

        return {"data": row_to_dict(updated_task), "message": "success", "code": 200}


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    with db_session() as db:
        task = db.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete related records in dependency order
        # Note: evaluations and feedbacks don't have task_id — they link via solution_id
        db.execute(
            "DELETE FROM evaluations WHERE solution_id IN (SELECT id FROM solutions WHERE task_id = ?)",
            (task_id,),
        )
        db.execute(
            "DELETE FROM feedbacks WHERE solution_id IN (SELECT id FROM solutions WHERE task_id = ?)",
            (task_id,),
        )
        db.execute("DELETE FROM solutions WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM analyses WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM workflows WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

        return {"message": "Task deleted successfully", "code": 200}
