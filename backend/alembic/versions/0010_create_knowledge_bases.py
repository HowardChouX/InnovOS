"""create knowledge_bases table

Revision ID: 0010
Revises: 0007
Create Date: 2026-07-30

知识库元数据表 — 每个 KB 的配置（embedding 模型、chunk size、检索模式等）。
FK 到 users(id) ON DELETE RESTRICT。
"""
from alembic import op

revision = "0010"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
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
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_bases_user_id "
        "ON knowledge_bases(user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_bases_user_id")
    op.execute("DROP TABLE IF EXISTS knowledge_bases")
