def init_patents(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            abstract TEXT DEFAULT '',
            applicants TEXT DEFAULT '[]',
            inventors TEXT DEFAULT '[]',
            filing_date TEXT DEFAULT '',
            publication_date TEXT DEFAULT '',
            patent_number TEXT DEFAULT '',
            publication_number TEXT DEFAULT '',
            priority_number TEXT DEFAULT '',
            ipc_codes TEXT DEFAULT '[]',
            claims TEXT DEFAULT '',
            description TEXT DEFAULT '',
            relevance_score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # Migration: add columns for existing databases
    for col in ['publication_number', 'priority_number', 'claims', 'description', 'created_at']:
        try:
            conn.execute(f"ALTER TABLE patents ADD COLUMN {col} TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists
