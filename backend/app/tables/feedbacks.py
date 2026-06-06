def init_feedbacks(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            solution_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            feedback_type TEXT NOT NULL DEFAULT 'general',
            comments TEXT DEFAULT '',
            is_applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (solution_id) REFERENCES solutions(id) ON DELETE CASCADE
        );
    """)
