"""backfill is_superuser from role=admin

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-29

一次性数据回填：把历史上 role='admin' 的用户提升为 is_superuser=TRUE，
保证 require_admin(判 role) → SuperUserDep(判 is_superuser) 迁移不锁死管理员。
UPDATE 天然幂等，可安全重跑。
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET is_superuser = TRUE WHERE role = 'admin'")


def downgrade() -> None:
    # 不自动降权，避免误伤；如需回滚手动处理
    pass
