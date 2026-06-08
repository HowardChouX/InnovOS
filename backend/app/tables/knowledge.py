import json

def init_knowledge_docs(conn):
    """保留旧表兼容"""
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
            base_id INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

def init_knowledge_items(conn):
    """CherryStudio 对齐的 knowledge_items 表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            base_id TEXT NOT NULL,
            group_id TEXT DEFAULT NULL,
            type TEXT NOT NULL CHECK(type IN ('file', 'url', 'note', 'directory')),
            data TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle'
                CHECK(status IN ('idle', 'preparing', 'processing', 'reading', 'embedding', 'completed', 'failed', 'deleting')),
            error TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_type_created
        ON knowledge_items(base_id, type, created_at);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_group_created
        ON knowledge_items(base_id, group_id, created_at);
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_groups (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
