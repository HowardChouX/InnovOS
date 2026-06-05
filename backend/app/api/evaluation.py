import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/{solution_id}")
def evaluate_solution(solution_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    sol = db.execute(
        "SELECT id FROM solutions WHERE id=? AND user_id=?",
        (solution_id, user["id"]),
    ).fetchone()
    if not sol:
        db.close()
        raise HTTPException(status_code=404, detail="Solution not found")

    existing = db.execute(
        "SELECT * FROM evaluations WHERE solution_id=? AND user_id=?",
        (solution_id, user["id"]),
    ).fetchone()
    if existing:
        db.close()
        return {
            "data": {
                "id": str(existing["id"]),
                "solutionId": str(existing["solution_id"]),
                "dimension": existing["dimension"],
                "score": existing["score"],
                "details": json.loads(existing["details"]),
                "status": existing["status"],
                "createdAt": existing["created_at"],
            },
            "message": "success", "code": 200,
        }

    raise HTTPException(status_code=400, detail="AI evaluation not available. Configure DEEPSEEK_API_KEY.")


@router.get("/{solution_id}/history")
def get_evaluation_history(solution_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evaluations WHERE solution_id=? AND user_id=? ORDER BY created_at DESC",
        (solution_id, user["id"]),
    ).fetchall()
    db.close()
    return {
        "data": [
            {
                "id": str(r["id"]),
                "solutionId": str(r["solution_id"]),
                "score": r["score"],
                "dimension": r["dimension"],
                "status": r["status"],
                "evaluatedAt": r["created_at"],
            }
            for r in rows
        ],
        "message": "success", "code": 200,
    }
