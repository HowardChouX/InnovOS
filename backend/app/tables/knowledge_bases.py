def init_knowledge_bases(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            group_id TEXT DEFAULT NULL,
            dimensions INTEGER DEFAULT NULL,
            embedding_model_id TEXT DEFAULT NULL,
            status TEXT DEFAULT 'completed' CHECK(status IN ('completed', 'failed')),
            error TEXT DEFAULT NULL,
            rerank_model_id TEXT DEFAULT NULL,
            file_processor_id TEXT DEFAULT NULL,
            chunk_size INTEGER DEFAULT 1024,
            chunk_overlap INTEGER DEFAULT 200,
            threshold REAL DEFAULT NULL,
            document_count INTEGER DEFAULT NULL,
            search_mode TEXT DEFAULT 'hybrid' CHECK(search_mode IN ('default', 'bm25', 'hybrid')),
            hybrid_alpha REAL DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 迁移旧表：如果存在旧结构的 knowledge_bases，保留数据
    try:
        conn.execute("SELECT id FROM knowledge_bases LIMIT 1")
        # 检查是否需要迁移旧 auto_increment 数据
        rows = conn.execute("SELECT id FROM knowledge_bases WHERE typeof(id) = 'integer' LIMIT 1").fetchone()
        if rows:
            # 旧数据是 integer，需要迁移到 text id
            # 这里简化处理：保留但后续创建新知识库用 uuid
            pass
    except Exception:
        pass
