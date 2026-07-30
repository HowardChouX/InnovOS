"""create system_settings table

Revision ID: 0015
Revises: 0007
Create Date: 2026-07-30

全局键值配置表(默认模型分配、Feature flag 等)。
无 FK。
"""
from alembic import op

revision = "0015"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_settings")
