def init_notifications(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'system',
            is_read INTEGER DEFAULT 0,
            is_recalled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    # 迁移：添加 is_recalled 列（如果不存在）
    try:
        conn.execute("SELECT is_recalled FROM notifications LIMIT 1")
    except Exception:
        conn.execute("ALTER TABLE notifications ADD COLUMN is_recalled INTEGER DEFAULT 0")
