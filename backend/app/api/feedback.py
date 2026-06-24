from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models.feedback import FeedbackCreate
from app.utils import utc_iso

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("")
def create_feedback(body: FeedbackCreate, user: dict = Depends(get_current_user)):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    db = get_db()
    sol = db.execute(
        "SELECT s.id FROM solutions s JOIN tasks t ON s.task_id = t.id WHERE s.id=? AND t.user_id=?",
        (body.solution_id, user["id"]),
    ).fetchone()
    if not sol:
        db.close()
        raise HTTPException(status_code=404, detail="Solution not found")

    row = db.execute(
        "INSERT INTO feedbacks (user_id, solution_id, rating, feedback_type, comments) VALUES (?,?,?,?,?) RETURNING *",
        (user["id"], body.solution_id, body.rating, body.feedback_type, body.comments),
    ).fetchone()
    db.commit()
    db.close()
    return {
        "data": {
            "id": str(row["id"]),
            "solutionId": str(row["solution_id"]),
            "rating": row["rating"],
            "feedbackType": row["feedback_type"],
            "comments": row["comments"],
            "createdAt": utc_iso(row["created_at"]),
        },
        "message": "success",
        "code": 200,
    }


@router.get("/{solution_id}")
def get_feedback(solution_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM feedbacks WHERE solution_id=? AND user_id=? ORDER BY created_at DESC",
        (solution_id, user["id"]),
    ).fetchall()
    db.close()
    return {
        "data": [
            {
                "id": str(r["id"]),
                "solutionId": str(r["solution_id"]),
                "rating": r["rating"],
                "feedbackType": r["feedback_type"],
                "comments": r["comments"],
                "createdAt": r["created_at"],
            }
            for r in rows
        ],
        "message": "success",
        "code": 200,
    }
