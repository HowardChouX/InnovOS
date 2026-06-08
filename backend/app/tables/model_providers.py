def init_model_providers(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            protocol TEXT DEFAULT 'openai',
            api_host TEXT NOT NULL,
            api_key_encrypted TEXT,
            api_model TEXT DEFAULT '',
            models JSON DEFAULT '[]',
            priority INTEGER DEFAULT 0,
            max_rpm INTEGER DEFAULT 60,
            current_rpm INTEGER DEFAULT 0,
            request_count INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            last_used_at TEXT,
            last_reset_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # 迁移：为已有表添加缺失列
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(model_providers)").fetchall()}
    for col, dtype in [
        ("api_model", 'TEXT DEFAULT ""'),
        ("priority", "INTEGER DEFAULT 0"),
        ("max_rpm", "INTEGER DEFAULT 60"),
        ("current_rpm", "INTEGER DEFAULT 0"),
        ("request_count", "INTEGER DEFAULT 0"),
        ("last_used_at", "TEXT"),
        ("last_reset_at", "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE model_providers ADD COLUMN {col} {dtype}")
