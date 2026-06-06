def init_knowledge_docs(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '未分类',
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT '',
            doc_type TEXT DEFAULT 'text',
            user_id INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            doc_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
