from datetime import datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.database import get_db

router = APIRouter(prefix="/api/sidebar", tags=["sidebar"])


@router.get("/stats")
def get_sidebar_stats(current_user: CurrentUser):
    """侧边栏统计数据（数据隔离）"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    if current_user.role == "admin":
        today_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE created_at::date=?", (today,)).fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
        analyzing = db.execute("SELECT COUNT(*) FROM tasks WHERE status='analyzing'").fetchone()[0]
    else:
        uid = current_user.id
        today_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND created_at::date=?",
            (uid, today),
        ).fetchone()[0]
        completed = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='completed'",
            (uid,),
        ).fetchone()[0]
        analyzing = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='analyzing'",
            (uid,),
        ).fetchone()[0]

    if current_user.role == "admin":
        patents = db.execute("SELECT COUNT(*) FROM patents").fetchone()[0]
    else:
        patents = 0  # non-admin users don't see global patent count

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
