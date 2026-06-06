from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/users", tags=["users"])


class UpdateUserInput(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class SendNotificationInput(BaseModel):
    user_id: int
    title: str
    content: str
    type: str = "system"


@router.get("")
def list_users(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    db = get_db()
    rows = db.execute(
        "SELECT id, username, email, role, is_active, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    
    return {
        "data": [
            {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "isActive": bool(row["is_active"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        "message": "success",
        "code": 200,
    }


@router.put("/{user_id}")
def update_user(user_id: int, body: UpdateUserInput, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    updates = []
    params = []
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if body.is_active else 0)
    if body.role is not None:
        if body.role not in ("admin", "user"):
            db.close()
            raise HTTPException(status_code=400, detail="Invalid role")
        updates.append("role = ?")
        params.append(body.role)
    
    if updates:
        params.extend([user_id])
        db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()
    
    row = db.execute("SELECT id, username, email, role, is_active, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    
    return {
        "data": {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
            "isActive": bool(row["is_active"]),
            "createdAt": row["created_at"],
        },
        "message": "success",
        "code": 200,
    }


@router.delete("/{user_id}")
def delete_user(user_id: int, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db = get_db()
    target = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    print(f"[DELETE USER] Deleting user {user_id} and related records")
    # Delete related records first to avoid foreign key constraint errors
    # analyses, solutions, workflows reference tasks(id)
    db.execute("DELETE FROM analyses WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)", (user_id,))
    db.execute("DELETE FROM workflows WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)", (user_id,))
    db.execute("DELETE FROM solutions WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)", (user_id,))
    db.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM evaluations WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM feedbacks WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM audit_logs WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    
    return {"data": None, "message": "deleted", "code": 200}
