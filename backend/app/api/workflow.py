import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/{task_id}")
def get_workflow(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    row = db.execute("SELECT * FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not yet started. Trigger analysis first.")

    return {
        "data": {
            "id": str(row["id"]), "taskId": str(row["task_id"]),
            "status": row["status"],
            "steps": json.loads(row["steps"]),
            "createdAt": row["created_at"],
        },
        "message": "success", "code": 200,
    }
