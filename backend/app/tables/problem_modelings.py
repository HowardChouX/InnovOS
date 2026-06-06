def init_problem_modelings(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS problem_modelings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL UNIQUE,
            problem_elements TEXT NOT NULL DEFAULT '{}',
            conflicts TEXT NOT NULL DEFAULT '[]',
            recommended_principles TEXT NOT NULL DEFAULT '[]',
            innovation_directions TEXT NOT NULL DEFAULT '[]',
            model_structure TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
    """)
