"""
通知服务层
"""
from app.database import get_db


class NotificationService:
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()[0]
        db.close()
        return count

    @staticmethod
    def mark_all_read(user_id: int):
        db = get_db()
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        db.commit()
        db.close()
