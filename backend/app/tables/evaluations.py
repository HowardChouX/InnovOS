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
            -- RootSeek 智枢评估维度
            root_cause_cut INTEGER DEFAULT 0,
            original_contradiction_resolved INTEGER DEFAULT 0,
            new_contradictions TEXT DEFAULT '[]',
            function_deficits_filled TEXT DEFAULT '[]',
            new_harmful_interactions TEXT DEFAULT '[]',
            ifr_distance TEXT DEFAULT 'far',
            ifr_gap_description TEXT DEFAULT '',
            ifr_parameters_achieved TEXT DEFAULT '[]',
            overall_verdict TEXT DEFAULT 'failed',
            evolution_alignment REAL DEFAULT 0,
            aligned_laws TEXT DEFAULT '[]',
            misaligned_laws TEXT DEFAULT '[]',
            maturity TEXT DEFAULT '概念阶段',
            confidence REAL DEFAULT NULL,
            FOREIGN KEY (solution_id) REFERENCES solutions(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
