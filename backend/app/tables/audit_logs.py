def init_audit_logs(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            detail TEXT DEFAULT '{}',
            ip_address TEXT DEFAULT '',
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
