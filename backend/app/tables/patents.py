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
            ipc_codes TEXT DEFAULT '[]',
            relevance_score INTEGER DEFAULT 0
        );
    """)
