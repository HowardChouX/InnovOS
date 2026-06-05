def init_workflows(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'running',
            steps TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
    """)
