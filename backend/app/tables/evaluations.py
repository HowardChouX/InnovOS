def init_evaluations(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solution_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            dimension TEXT NOT NULL DEFAULT 'comprehensive',
            score REAL DEFAULT 0,
            details TEXT DEFAULT '{}',
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (solution_id) REFERENCES solutions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
