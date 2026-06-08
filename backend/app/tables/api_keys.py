def init_api_keys(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id TEXT DEFAULT '',
            key_name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            api_base_url TEXT DEFAULT 'https://api.deepseek.com',
            api_model TEXT DEFAULT 'deepseek-chat',
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            max_rpm INTEGER DEFAULT 60,
            current_rpm INTEGER DEFAULT 0,
            last_reset_at TEXT,
            last_used_at TEXT,
            request_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # 迁移：添加 provider_id 列（如果不存在）
    try:
        conn.execute("SELECT provider_id FROM api_keys LIMIT 1")
    except Exception:
        conn.execute("ALTER TABLE api_keys ADD COLUMN provider_id TEXT DEFAULT ''")