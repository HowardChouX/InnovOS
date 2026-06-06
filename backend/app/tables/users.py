def init_users(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # 为已存在的表添加role字段（如果不存在）
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except Exception:
        pass
