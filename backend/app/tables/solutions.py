def init_solutions(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            principles TEXT DEFAULT '[]',
            confidence_score INTEGER DEFAULT 0,
            patent_references TEXT DEFAULT '[]',
            rating INTEGER DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
    """)
