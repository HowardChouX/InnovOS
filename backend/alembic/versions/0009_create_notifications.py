"""create notifications table

Revision ID: 0009
Revises: 0007
Create Date: 2026-07-30

通知表 — 系统通知、流程通知、专利通知、告警等。
FK 到 users(id) ON DELETE RESTRICT(不允许删除有通知的用户)。
is_read/is_recalled 列为 BOOLEAN 前置，无需后续 ALTER。
"""
from alembic import op

revision = "0009"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'system',
            is_read BOOLEAN DEFAULT FALSE,
            is_recalled BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_id")
    op.execute("DROP TABLE IF EXISTS notifications")
