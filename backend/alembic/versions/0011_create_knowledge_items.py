"""create knowledge_items table

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-30

知识库条目表 — KB 内每个文档/分段的状态与数据。
FK 到 knowledge_bases(id) ON DELETE CASCADE。
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            base_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            group_id TEXT DEFAULT NULL,
            type TEXT NOT NULL,
            data TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle',
            error TEXT DEFAULT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_type_created "
        "ON knowledge_items(base_id, type, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_group_created "
        "ON knowledge_items(base_id, group_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_base_id "
        "ON knowledge_items(base_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_items_status "
        "ON knowledge_items(status)"
    )


def downgrade() -> None:
    for idx in (
        "idx_knowledge_items_status",
        "idx_knowledge_items_base_id",
        "idx_knowledge_items_base_group_created",
        "idx_knowledge_items_base_type_created",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.execute("DROP TABLE IF EXISTS knowledge_items")
