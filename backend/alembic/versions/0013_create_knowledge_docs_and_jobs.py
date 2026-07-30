"""create knowledge_docs and knowledge_jobs tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-30

包含两张表：
- knowledge_docs: 知识库文档元数据(独立文档概念)
- knowledge_jobs: 知识库作业系统持久化(用于崩溃恢复)
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── knowledge_docs ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '未分类',
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT '',
            doc_type TEXT DEFAULT 'text',
            user_id INTEGER NOT NULL REFERENCES users(id),
            base_id INTEGER DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_docs_user_active "
        "ON knowledge_docs(user_id, is_active)"
    )

    # ── knowledge_jobs ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            queue TEXT NOT NULL,
            input_data TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            timeout_ms INTEGER NOT NULL DEFAULT 600000,
            parent_job_id TEXT DEFAULT NULL,
            idempotency_key TEXT DEFAULT NULL,
            error TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_queue_status "
        "ON knowledge_jobs(queue, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_idempotency "
        "ON knowledge_jobs(idempotency_key)"
    )
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_jobs_idempotency_unique
        ON knowledge_jobs(idempotency_key)
        WHERE idempotency_key IS NOT NULL AND idempotency_key != ''
    """)


def downgrade() -> None:
    # knowledge_jobs
    for idx in (
        "idx_knowledge_jobs_idempotency_unique",
        "idx_knowledge_jobs_idempotency",
        "idx_knowledge_jobs_queue_status",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.execute("DROP TABLE IF EXISTS knowledge_jobs")

    # knowledge_docs
    op.execute("DROP INDEX IF EXISTS idx_knowledge_docs_user_active")
    op.execute("DROP TABLE IF EXISTS knowledge_docs")
