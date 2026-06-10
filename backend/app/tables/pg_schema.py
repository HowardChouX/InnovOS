"""
Database schema — dual-mode: PostgreSQL / SQLite.

Auto-detects backend from the connection object.
PostgreSQL:
  - SERIAL PRIMARY KEY, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
  - information_schema.columns for migration
SQLite:
  - INTEGER PRIMARY KEY AUTOINCREMENT, datetime('now')
  - PRAGMA table_info for migration
"""
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Backend detection helpers
# ═══════════════════════════════════════════════════════════════

def _is_sqlite(db) -> bool:
    return isinstance(db._conn, sqlite3.Connection)


def _serial(prefix: str = "") -> str:
    return f"{prefix}INTEGER PRIMARY KEY AUTOINCREMENT"  # fallback for non-PG


def _now() -> str:
    return "datetime('now')"


def _ensure_columns(db, table: str, columns: list[tuple[str, str]]):
    """确保表中存在指定列，缺失则添加（兼容 SQLite + PostgreSQL）。"""
    if _is_sqlite(db):
        existing = {
            r["name"]
            for r in db.execute(f"PRAGMA table_info({table})").fetchall()
        }
    else:
        existing = {
            r["column_name"]
            for r in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                (table,),
            ).fetchall()
        }
    for col_name, col_def in columns:
        if col_name not in existing:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                logger.info(f"  + 添加列 {table}.{col_name}")
            except Exception as e:
                logger.warning(f"  无法添加列 {table}.{col_name}: {e}")


def _ddl_int_pk() -> str:
    """Primary key type: SERIAL for PG, INTEGER for SQLite."""
    return "SERIAL PRIMARY KEY"


def _ddl_now() -> str:
    """Default timestamp expression."""
    return "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"


# ═══════════════════════════════════════════════════════════════
#  Per-table DDL
# ═══════════════════════════════════════════════════════════════

def init_users(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            email TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ({now})
        );
    """)
    _ensure_columns(db, "users", [
        ("role", "TEXT DEFAULT 'user'"),
        ("email", "TEXT DEFAULT ''"),
        ("is_active", "INTEGER DEFAULT 1"),
    ])


def init_tasks(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS tasks (
            id {pk},
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)


def init_analyses(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS analyses (
            id {pk},
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            center_node TEXT NOT NULL DEFAULT '{{}}',
            satellite_nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            principles TEXT NOT NULL DEFAULT '[]'
        );
    """)


def init_solutions(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS solutions (
            id {pk},
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            principles TEXT DEFAULT '[]',
            confidence_score INTEGER DEFAULT 0,
            patent_references TEXT DEFAULT '[]',
            rating INTEGER DEFAULT 0
        );
    """)


def init_workflows(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS workflows (
            id {pk},
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'running',
            steps TEXT DEFAULT '[]',
            created_at TEXT DEFAULT ({now})
        );
    """)


def init_patents(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS patents (
            id {pk},
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


def init_evaluations(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS evaluations (
            id {pk},
            solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            dimension TEXT NOT NULL DEFAULT 'comprehensive',
            score REAL DEFAULT 0,
            details TEXT DEFAULT '{{}}',
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT ({now}),
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
            confidence REAL DEFAULT NULL
        );
    """)


def init_feedbacks(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id {pk},
            user_id INTEGER NOT NULL REFERENCES users(id),
            solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            feedback_type TEXT DEFAULT 'general',
            comments TEXT DEFAULT '',
            is_applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ({now})
        );
    """)


def init_audit_logs(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id {pk},
            user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            detail TEXT DEFAULT '{{}}',
            ip_address TEXT DEFAULT '',
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT ({now})
        );
    """)


def init_api_keys(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS api_keys (
            id {pk},
            provider_id TEXT DEFAULT '',
            key_name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            api_base_url TEXT DEFAULT 'https://api.deepseek.com',
            api_model TEXT DEFAULT 'deepseek-chat',
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            max_rpm INTEGER DEFAULT 60,
            current_rpm INTEGER DEFAULT 0,
            last_reset_at TEXT,
            last_used_at TEXT,
            request_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ({now})
        );
    """)
    _ensure_columns(db, "api_keys", [
        ("provider_id", "TEXT DEFAULT ''"),
    ])


def init_notifications(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS notifications (
            id {pk},
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'system',
            is_read INTEGER DEFAULT 0,
            is_recalled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ({now})
        );
    """)
    _ensure_columns(db, "notifications", [
        ("is_recalled", "INTEGER DEFAULT 0"),
    ])


def init_knowledge_bases(db):
    is_sql = _is_sqlite(db)
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            group_id TEXT DEFAULT NULL,
            dimensions INTEGER DEFAULT NULL,
            embedding_model_id TEXT DEFAULT NULL,
            status TEXT DEFAULT 'completed',
            error TEXT DEFAULT NULL,
            rerank_model_id TEXT DEFAULT NULL,
            file_processor_id TEXT DEFAULT NULL,
            chunk_size INTEGER DEFAULT 1024,
            chunk_overlap INTEGER DEFAULT 200,
            threshold REAL DEFAULT NULL,
            document_count INTEGER DEFAULT NULL,
            search_mode TEXT DEFAULT 'hybrid',
            hybrid_alpha REAL DEFAULT NULL,
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)


def init_knowledge_items(db):
    is_sql = _is_sqlite(db)
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            base_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            group_id TEXT DEFAULT NULL,
            type TEXT NOT NULL,
            data TEXT NOT NULL DEFAULT '{{}}',
            status TEXT NOT NULL DEFAULT 'idle',
            error TEXT DEFAULT NULL,
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_type_created
        ON knowledge_items(base_id, type, created_at);
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_group_created
        ON knowledge_items(base_id, group_id, created_at);
    """)


def init_knowledge_items_pgvector(db):
    """向量存储 — Cherry Studio 模式：base_id + item_id 关联 knowledge_items。"""
    is_sql = _is_sqlite(db)
    if is_sql:
        logger.info("SQLite vector store — base_id + item_id schema")
        now = "datetime('now')"
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                base_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                embedding BLOB,
                created_at TEXT DEFAULT ({now})
            );
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_base_item
            ON knowledge_vectors(base_id, item_id);
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_user_base
            ON knowledge_vectors(user_id, base_id);
        """)
    else:
        db.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        now = "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_vectors (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                base_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                embedding vector(4096),
                created_at TEXT DEFAULT ({now})
            );
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_base_item
            ON knowledge_vectors(base_id, item_id);
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_user_base
            ON knowledge_vectors(user_id, base_id);
        """)


def init_knowledge_jobs(db):
    """知识库作业表 — 用于作业系统的持久化和崩溃恢复"""
    is_sql = _is_sqlite(db)
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            queue TEXT NOT NULL,
            input_data TEXT NOT NULL DEFAULT '{{}}',
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            timeout_ms INTEGER NOT NULL DEFAULT 600000,
            parent_job_id TEXT DEFAULT NULL,
            idempotency_key TEXT DEFAULT NULL,
            error TEXT DEFAULT NULL,
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_queue_status
        ON knowledge_jobs(queue, status);
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_idempotency
        ON knowledge_jobs(idempotency_key);
    """)
    logger.info("Initialized knowledge_jobs table")


def init_knowledge_groups(db):
    is_sql = _is_sqlite(db)
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_groups (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)


def init_knowledge_docs(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id {pk},
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '未分类',
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT '',
            doc_type TEXT DEFAULT 'text',
            user_id INTEGER NOT NULL REFERENCES users(id),
            base_id INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ({now}),
            updated_at TEXT DEFAULT ({now})
        );
    """)


def init_problem_modelings(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS problem_modelings (
            id {pk},
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            problem_elements TEXT NOT NULL DEFAULT '{{}}',
            conflicts TEXT NOT NULL DEFAULT '[]',
            recommended_principles TEXT NOT NULL DEFAULT '[]',
            innovation_directions TEXT NOT NULL DEFAULT '[]',
            model_structure TEXT NOT NULL DEFAULT '{{}}'
        );
    """)


def init_system_settings(db):
    """system_settings 表 — 全局键值配置（如默认模型分配）。"""
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS system_settings (
            id {pk},
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL DEFAULT '{{}}',
            updated_at TEXT DEFAULT ({now})
        );
    """)


def init_models(db):
    """models 表 — 独立模型配置（替代 model_providers.models JSON 列）。"""
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS models (
            id {pk},
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            capabilities TEXT DEFAULT '[]',
            endpoint_types TEXT DEFAULT '[]',
            context_window INTEGER DEFAULT 0,
            max_output_tokens INTEGER DEFAULT 0,
            max_input_tokens INTEGER DEFAULT 0,
            model_group TEXT DEFAULT '',
            is_enabled INTEGER DEFAULT 1,
            metadata TEXT DEFAULT '{{}}'
        );
    """)
    # Add unique constraint separately for SQLite compatibility
    try:
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_models_provider_model
            ON models(provider_id, model_id)
        """)
    except Exception:
        pass
    _migrate_models_from_json_column(db)


def _migrate_models_from_json_column(db):
    """从 model_providers.models JSON 列迁移数据到 models 表（幂等）。"""
    is_sql = _is_sqlite(db)
    if is_sql:
        rows = db.execute(
            "SELECT provider_id, models FROM model_providers WHERE models IS NOT NULL AND models != '[]'"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT provider_id, models FROM model_providers WHERE models IS NOT NULL AND models::text != '[]'"
        ).fetchall()
    migrated = 0
    for row in rows:
        pid = row["provider_id"]
        raw = json.loads(row["models"]) if isinstance(row["models"], str) else row["models"]
        for entry in raw or []:
            mid = entry.get("id") if isinstance(entry, dict) else entry
            if not mid:
                continue
            caps = json.dumps(entry.get("capabilities", [])) if isinstance(entry, dict) else "[]"
            try:
                if is_sql:
                    db.execute(
                        """INSERT OR IGNORE INTO models (provider_id, model_id, capabilities)
                           VALUES (?, ?, ?)""",
                        (pid, mid, caps),
                    )
                else:
                    db.execute(
                        """INSERT INTO models (provider_id, model_id, capabilities)
                           VALUES (?, ?, ?)
                           ON CONFLICT (provider_id, model_id) DO NOTHING""",
                        (pid, mid, caps),
                    )
                migrated += 1
            except Exception as e:
                logger.warning(f"迁移 models 数据失败: {pid}/{mid}: {e}")
    if migrated:
        logger.info(f"迁移了 {migrated} 个模型到 models 表")


def init_model_providers(db):
    is_sql = _is_sqlite(db)
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sql else "SERIAL PRIMARY KEY"
    now = "datetime('now')" if is_sql else "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS model_providers (
            id {pk},
            provider_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            protocol TEXT DEFAULT 'openai',
            api_host TEXT NOT NULL,
            api_key_encrypted TEXT,
            api_model TEXT DEFAULT '',
            models TEXT DEFAULT '[]',
            max_rpm INTEGER DEFAULT 60,
            current_rpm INTEGER DEFAULT 0,
            request_count INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            last_used_at TEXT,
            last_reset_at TEXT,
            created_at TEXT DEFAULT ({now})
        );
    """)
    _ensure_columns(db, "model_providers", [
        ("api_model", "TEXT DEFAULT ''"),
        ("max_rpm", "INTEGER DEFAULT 60"),
        ("current_rpm", "INTEGER DEFAULT 0"),
        ("request_count", "INTEGER DEFAULT 0"),
        ("last_used_at", "TEXT"),
        ("last_reset_at", "TEXT"),
    ])
    # 迁移：删除废弃的 priority 列
    try:
        is_sql = _is_sqlite(db)
        if is_sql:
            # Check if column exists before dropping
            cols = {r["name"] for r in db.execute("PRAGMA table_info(model_providers)").fetchall()}
            if "priority" in cols:
                db.execute("ALTER TABLE model_providers DROP COLUMN priority")
                logger.info("  - 移除 model_providers.priority 列")
        else:
            db.execute("ALTER TABLE model_providers DROP COLUMN IF EXISTS priority")
            logger.info("  - 移除 model_providers.priority 列")
    except Exception as e:
        logger.warning(f"  无法移除 priority 列: {e}")


# ═══════════════════════════════════════════════════════════════
#  Unified entry point
# ═══════════════════════════════════════════════════════════════

def init_all_tables(db):
    """按依赖顺序初始化所有表。"""
    is_sql = _is_sqlite(db)
    backend = "SQLite" if is_sql else "PostgreSQL"
    logger.info(f"Initializing {backend} schema...")
    init_users(db)
    init_tasks(db)
    init_analyses(db)
    init_solutions(db)
    init_workflows(db)
    init_patents(db)
    init_evaluations(db)
    init_feedbacks(db)
    init_audit_logs(db)
    init_api_keys(db)
    init_notifications(db)
    init_knowledge_bases(db)
    init_knowledge_items(db)
    init_knowledge_groups(db)
    init_knowledge_jobs(db)
    init_knowledge_docs(db)
    init_knowledge_items_pgvector(db)
    init_problem_modelings(db)
    init_system_settings(db)
    init_model_providers(db)
    init_models(db)
    logger.info(f"{backend} schema initialization complete")
