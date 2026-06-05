import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/solutions", tags=["solutions"])


class UpdateSolutionInput(BaseModel):
    rating: Optional[int] = None


def row_to_dict(r):
    return {
        "id": str(r["id"]), "taskId": str(r["task_id"]),
        "title": r["title"], "description": r["description"],
        "principles": json.loads(r["principles"]),
        "confidenceScore": r["confidence_score"],
        "patentReferences": json.loads(r["patent_references"]),
        "rating": r["rating"],
    }


@router.get("/{task_id}")
def get_solutions(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.execute("SELECT * FROM solutions WHERE task_id=?", (task_id,)).fetchall()
    db.close()
    return {"data": [row_to_dict(r) for r in rows], "message": "success", "code": 200}


@router.get("/{task_id}/{solution_id}")
def get_solution_detail(task_id: int, solution_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    row = db.execute(
        "SELECT * FROM solutions WHERE id=? AND task_id=?", (solution_id, task_id)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Solution not found")
    return {"data": row_to_dict(row), "message": "success", "code": 200}


@router.put("/{task_id}/{solution_id}")
def update_solution(
    task_id: int, solution_id: int,
    body: UpdateSolutionInput,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    row = db.execute(
        "SELECT * FROM solutions WHERE id=? AND task_id=?", (solution_id, task_id)
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Solution not found")

    if body.rating is not None:
        if body.rating < 1 or body.rating > 5:
            db.close()
            raise HTTPException(status_code=400, detail="Rating must be 1-5")
        db.execute("UPDATE solutions SET rating=? WHERE id=?", (body.rating, solution_id))
        db.commit()

    row = db.execute("SELECT * FROM solutions WHERE id=?", (solution_id,)).fetchone()
    db.close()
    return {"data": row_to_dict(row), "message": "success", "code": 200}
