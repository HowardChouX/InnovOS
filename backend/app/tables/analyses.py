def init_analyses(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL UNIQUE,
            center_node TEXT NOT NULL DEFAULT '{}',
            satellite_nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            principles TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
    """)
