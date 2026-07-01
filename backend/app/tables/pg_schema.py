"""
Database schema — PostgreSQL only.
Uses SERIAL PRIMARY KEY, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
and information_schema.columns for migration.
"""

import json
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  DDL helpers
# ═══════════════════════════════════════════════════════════════


def _ddl_int_pk() -> str:
    """Primary key type: SERIAL PRIMARY KEY for PG."""
    return "SERIAL PRIMARY KEY"


def _ddl_now() -> str:
    """Default timestamp expression for PG."""
    return "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"


def _ensure_columns(db, table: str, columns: list[tuple[str, str]]):
    """确保表中存在指定列，缺失则添加（PostgreSQL）。"""
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


# ═══════════════════════════════════════════════════════════════
#  Per-table DDL
# ═══════════════════════════════════════════════════════════════


def init_users(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    _ensure_columns(
        db,
        "users",
        [
            ("role", "TEXT DEFAULT 'user'"),
            ("email", "TEXT DEFAULT ''"),
            ("is_active", "INTEGER DEFAULT 1"),
        ],
    )
    _ensure_columns(
        db,
        "users",
        [
            ("token_version", "INTEGER DEFAULT 0"),
        ],
    )


def seed_admin_user(db):
    """注入一条 id=0 的管理员记录，确保 FK 约束（tasks.user_id→users.id）对 env 管理员可用。

    仅在首次启动时执行一次，后续 on conflict 跳过。
    """
    from app.core.config import settings

    username = settings.FIRST_SUPERUSER or "admin"
    db.execute(
        """INSERT INTO users (id, username, password_hash, role, email, is_active, created_at)
           VALUES (0, ?, '', 'admin', '', 1, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
           ON CONFLICT (id) DO NOTHING""",
        (username,),
    )
    db.commit()


def init_tasks(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    pk = _ddl_int_pk()
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
    pk = _ddl_int_pk()
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
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    pk = _ddl_int_pk()
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
            relevance_score INTEGER DEFAULT 0,
            publication_number TEXT DEFAULT '',
            claims TEXT DEFAULT '',
            description TEXT DEFAULT ''
        );
    """)


def init_evaluations(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    pk = _ddl_int_pk()
    now = _ddl_now()
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


def init_audit_log(db):
    """审计日志表 — 记录所有破坏性操作以便安全审查。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT '',
            resource_id TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")


def init_api_keys(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    _ensure_columns(
        db,
        "api_keys",
        [
            ("provider_id", "TEXT DEFAULT ''"),
        ],
    )


def init_notifications(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    _ensure_columns(
        db,
        "notifications",
        [
            ("is_recalled", "INTEGER DEFAULT 0"),
        ],
    )


def init_knowledge_bases(db):
    now = _ddl_now()
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
    now = _ddl_now()
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
    """向量存储 — pgvector 模式：base_id + item_id 关联 knowledge_items。"""
    db.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    now = _ddl_now()
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
    now = _ddl_now()
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
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_jobs_idempotency_unique
        ON knowledge_jobs(idempotency_key)
        WHERE idempotency_key IS NOT NULL AND idempotency_key != '';
    """)
    logger.info("Initialized knowledge_jobs table")


def init_knowledge_groups(db):
    now = _ddl_now()
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
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    pk = _ddl_int_pk()
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
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    pk = _ddl_int_pk()
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
    import contextlib

    with contextlib.suppress(Exception):
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_models_provider_model
            ON models(provider_id, model_id)
        """)
    _migrate_models_from_json_column(db)


def _migrate_models_from_json_column(db):
    """从 model_providers.models JSON 列迁移数据到 models 表（幂等）。"""
    try:
        rows = db.execute(
            "SELECT provider_id, models FROM model_providers WHERE models IS NOT NULL AND models::text != '[]'"
        ).fetchall()
    except Exception:
        logger.debug("model_providers.models 列不存在或已废弃，跳过迁移")
        return
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
                db.execute(
                    """INSERT INTO models (provider_id, model_id, capabilities)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (provider_id, model_id) DO NOTHING""",
                    (pid, mid, caps),
                )
                migrated += 1
            except Exception as e:
                logger.warning(f"迁移 models 数据失败: {pid}/{mid}: {e}")
    if migrated:
        logger.info(f"迁移了 {migrated} 个模型到 models 表")


def init_model_providers(db):
    pk = _ddl_int_pk()
    now = _ddl_now()
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
    _ensure_columns(
        db,
        "model_providers",
        [
            ("api_model", "TEXT DEFAULT ''"),
            ("max_rpm", "INTEGER DEFAULT 60"),
            ("current_rpm", "INTEGER DEFAULT 0"),
            ("request_count", "INTEGER DEFAULT 0"),
            ("last_used_at", "TEXT"),
            ("last_reset_at", "TEXT"),
        ],
    )
    # 迁移：删除废弃的 priority 列
    try:
        db.execute("ALTER TABLE model_providers DROP COLUMN IF EXISTS priority")
        logger.info("  - 移除 model_providers.priority 列")
    except Exception as e:
        logger.warning(f"  无法移除 priority 列: {e}")


# ═══════════════════════════════════════════════════════════════
#  Unified entry point
# ═══════════════════════════════════════════════════════════════


def init_all_tables(db):
    """按依赖顺序初始化所有表。"""
    logger.info("Initializing PostgreSQL schema...")
    # pgvector 扩展必须最先创建
    db.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    logger.info("pgvector extension ready")
    init_users(db)
    _ensure_columns(db, "users", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_tasks(db)
    init_analyses(db)
    _ensure_columns(db, "analyses", [("created_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    _ensure_columns(db, "analyses", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_solutions(db)
    _ensure_columns(db, "solutions", [("created_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    _ensure_columns(db, "solutions", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_workflows(db)
    _ensure_columns(db, "workflows", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_patents(db)
    _ensure_columns(db, "patents", [("created_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    _ensure_columns(
        db,
        "patents",
        [
            ("publication_number", "TEXT DEFAULT ''"),
            ("claims", "TEXT DEFAULT ''"),
            ("description", "TEXT DEFAULT ''"),
        ],
    )
    _ensure_columns(db, "patents", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    # ── UNIQUE index on patent_number ──
    try:
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_patents_patent_number
            ON patents(patent_number) WHERE patent_number != ''
        """)
        logger.info("  + 创建 patents.patent_number 唯一索引")
    except Exception as e:
        logger.warning(f"  无法创建 patent_number 索引: {e}")

    init_evaluations(db)
    _ensure_columns(db, "evaluations", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_feedbacks(db)
    _ensure_columns(db, "feedbacks", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_audit_log(db)
    _ensure_columns(db, "audit_log", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_api_keys(db)
    _ensure_columns(db, "api_keys", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_notifications(db)
    _ensure_columns(db, "notifications", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_knowledge_bases(db)
    init_knowledge_items(db)
    init_knowledge_groups(db)
    init_knowledge_jobs(db)
    init_knowledge_docs(db)
    init_knowledge_items_pgvector(db)
    # ── pgvector HNSW index for efficient similarity search ──
    try:
        db.execute("SAVEPOINT sp_hnsw")
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_embedding
            ON knowledge_vectors USING hnsw (embedding vector_cosine_ops)
        """)
        db.execute("RELEASE SAVEPOINT sp_hnsw")
        logger.info("  + 创建 knowledge_vectors.embedding HNSW 索引")
    except Exception as e:
        db.execute("ROLLBACK TO SAVEPOINT sp_hnsw")
        logger.warning(f"  HNSW 索引创建失败（可能 pgvector 版本不支持）: {e}")

    init_problem_modelings(db)
    _ensure_columns(db, "problem_modelings", [("created_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    _ensure_columns(db, "problem_modelings", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    init_system_settings(db)
    init_model_providers(db)
    _ensure_columns(db, "model_providers", [("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))")])
    # ── Drop deprecated columns ───────────────────────────
    try:
        db.execute("ALTER TABLE model_providers DROP COLUMN IF EXISTS api_key_encrypted")
        logger.info("  - 移除 model_providers.api_key_encrypted（废弃列）")
    except Exception as e:
        logger.warning(f"  无法移除 api_key_encrypted: {e}")

    init_models(db)
    _ensure_columns(
        db,
        "models",
        [
            ("created_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))"),
            ("updated_at", "TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))"),
        ],
    )

    # ── Foreign Key constraints ──────────────────────────────────
    logger.info("Adding foreign key constraints...")

    for fk_name, fk_sql in [
        (
            "fk_kv_item",
            """
            ALTER TABLE knowledge_vectors
            ADD CONSTRAINT fk_kv_item
            FOREIGN KEY (item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
        """,
        ),
        (
            "fk_kv_base",
            """
            ALTER TABLE knowledge_vectors
            ADD CONSTRAINT fk_kv_base
            FOREIGN KEY (base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        """,
        ),
    ]:
        try:
            db.execute("SAVEPOINT sp_fk")
            db.execute(fk_sql)
            db.execute("RELEASE SAVEPOINT sp_fk")
            logger.info(f"FK {fk_name} added")
        except Exception:
            db.execute("ROLLBACK TO SAVEPOINT sp_fk")
            logger.debug(f"FK {fk_name} already exists")

    # ── FK: knowledge_items.group_id (removed — column is also used for tree parent UUIDs) ──
    try:
        db.execute("SAVEPOINT sp_drop_fk_group")
        db.execute("ALTER TABLE knowledge_items DROP CONSTRAINT IF EXISTS fk_ki_group")
        db.execute("RELEASE SAVEPOINT sp_drop_fk_group")
        logger.info("  - Removed FK fk_ki_group (group_id is not always knowledge_groups.id)")
    except Exception:
        db.execute("ROLLBACK TO SAVEPOINT sp_drop_fk_group")
        logger.debug("  FK fk_ki_group did not exist")

    # ── Performance indexes ──────────────────────────────────────
    logger.info("Creating performance indexes...")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_item_id ON knowledge_vectors(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_analyses_task_id ON analyses(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_solutions_task_id ON solutions(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_bases_user_id ON knowledge_bases(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_id ON knowledge_items(base_id)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_status ON knowledge_items(status)",
        "CREATE INDEX IF NOT EXISTS idx_workflows_task_id ON workflows(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_evaluations_solution_user ON evaluations(solution_id, user_id)",
        "CREATE INDEX IF NOT EXISTS idx_feedbacks_solution_user ON feedbacks(solution_id, user_id)",
        "CREATE INDEX IF NOT EXISTS idx_problem_modelings_task_id ON problem_modelings(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_groups_user_id ON knowledge_groups(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_docs_user_active ON knowledge_docs(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_patents_relevance_score ON patents(relevance_score DESC)",
    ]

    for idx_sql in indexes:
        try:
            db.execute("SAVEPOINT sp_idx")
            db.execute(idx_sql)
            db.execute("RELEASE SAVEPOINT sp_idx")
        except Exception as e:
            db.execute("ROLLBACK TO SAVEPOINT sp_idx")
            logger.warning(f"Index creation skipped: {e}")

    # ── BOOLEAN column type migration ─────────────────────────────
    # 将 INTEGER 0/1 列迁移为原生 BOOLEAN 类型
    logger.info("Migrating INTEGER → BOOLEAN columns...")

    # is_active 列迁移（多个表）
    try:
        db.execute("SAVEPOINT sp_bool_migrate")
        db.execute("ALTER TABLE users ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("ALTER TABLE tasks ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("ALTER TABLE notifications ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("ALTER TABLE knowledge_items ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("ALTER TABLE knowledge_docs ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("ALTER TABLE knowledge_bases ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
        db.execute("RELEASE SAVEPOINT sp_bool_migrate")
        logger.info("  + 迁移 is_active INTEGER → BOOLEAN")
    except Exception as e:
        db.execute("ROLLBACK TO SAVEPOINT sp_bool_migrate")
        logger.debug(f"  is_active 已为 BOOLEAN 或无法迁移: {e}")

    # notifications 其他布尔列
    try:
        db.execute("SAVEPOINT sp_bool_notif")
        db.execute("ALTER TABLE notifications ALTER COLUMN is_read TYPE BOOLEAN USING is_read::boolean")
        db.execute("ALTER TABLE notifications ALTER COLUMN is_recalled TYPE BOOLEAN USING is_recalled::boolean")
        db.execute("RELEASE SAVEPOINT sp_bool_notif")
        logger.info("  + 迁移 notifications is_read/is_recalled INTEGER → BOOLEAN")
    except Exception as e:
        db.execute("ROLLBACK TO SAVEPOINT sp_bool_notif")
        logger.debug(f"  notifications 布尔列无法迁移: {e}")

    # evaluations 布尔列
    try:
        db.execute("SAVEPOINT sp_bool_eval")
        db.execute("ALTER TABLE evaluations ALTER COLUMN root_cause_cut TYPE BOOLEAN USING root_cause_cut::boolean")
        db.execute("ALTER TABLE evaluations ALTER COLUMN original_contradiction_resolved TYPE BOOLEAN USING original_contradiction_resolved::boolean")
        db.execute("RELEASE SAVEPOINT sp_bool_eval")
        logger.info("  + 迁移 evaluations 布尔列 INTEGER → BOOLEAN")
    except Exception as e:
        db.execute("ROLLBACK TO SAVEPOINT sp_bool_eval")
        logger.debug(f"  evaluations 布尔列无法迁移: {e}")

    logger.info("Schema migration complete")
