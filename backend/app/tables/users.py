def init_users(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            email TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # 为已存在的表添加字段（如果不存在）
    for col, default in [
        ("role", "TEXT DEFAULT 'user'"),
        ("email", "TEXT DEFAULT ''"),
        ("is_active", "INTEGER DEFAULT 1"),
    ]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {default}")
        except Exception:
            pass
