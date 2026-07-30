"""create audit_log table

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-30

审计日志表 — 记录所有破坏性操作以便安全审查。
FK 到 users(id) ON DELETE SET NULL(用户被删后保留日志)。
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT '',
            resource_id TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audit_log_created")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_action")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_user")
    op.execute("DROP TABLE IF EXISTS audit_log")
