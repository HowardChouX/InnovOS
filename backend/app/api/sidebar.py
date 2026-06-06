from datetime import datetime
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/sidebar", tags=["sidebar"])


@router.get("/stats")
def get_sidebar_stats(user: dict = Depends(get_current_user)):
    """侧边栏统计数据（数据隔离）"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    if user["role"] == "admin":
        today_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE date(created_at)=?", (today,)
        ).fetchone()[0]
        completed = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='completed'"
        ).fetchone()[0]
        analyzing = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='analyzing'"
        ).fetchone()[0]
    else:
        today_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND date(created_at)=?",
            (user["id"], today),
        ).fetchone()[0]
        completed = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='completed'",
            (user["id"],),
        ).fetchone()[0]
        analyzing = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='analyzing'",
            (user["id"],),
        ).fetchone()[0]

    patents = db.execute("SELECT COUNT(*) FROM patents").fetchone()[0]

    db.close()

    return {
        "data": {
            "todayTasks": today_tasks,
            "completedTasks": completed,
            "analyzingTasks": analyzing,
            "patentCount": patents,
        },
        "message": "success",
    }
