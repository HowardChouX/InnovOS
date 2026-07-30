"""create knowledge_groups table

Revision ID: 0012
Revises: 0007
Create Date: 2026-07-30

知识库分组表 — 用于组织管理多个 KB。
FK 到 users(id) ON DELETE RESTRICT。
"""
from alembic import op

revision = "0012"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_groups (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_groups_user_id "
        "ON knowledge_groups(user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_groups_user_id")
    op.execute("DROP TABLE IF EXISTS knowledge_groups")
