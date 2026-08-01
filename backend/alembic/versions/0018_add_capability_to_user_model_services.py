"""add capability column to user_model_services

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 capability 列（现有行默认 chat）
    op.execute("""
        ALTER TABLE user_model_services
        ADD COLUMN IF NOT EXISTS capability TEXT NOT NULL DEFAULT 'chat'
    """)
    # 2. 删旧主键 + 唯一约束
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS user_model_services_pkey")
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS user_model_services_user_id_failover_order_key")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_enabled")
    # 3. 建新主键 + 唯一约束 + 索引
    op.execute("""
        ALTER TABLE user_model_services
        ADD PRIMARY KEY (user_id, provider_id, capability)
    """)
    op.execute("""
        ALTER TABLE user_model_services
        ADD CONSTRAINT uq_ums_user_cap_order UNIQUE (user_id, capability, failover_order)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ums_user_cap_enabled
            ON user_model_services (user_id, capability, is_enabled, failover_order)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS uq_ums_user_cap_order")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_cap_enabled")
    op.execute("ALTER TABLE user_model_services DROP COLUMN IF EXISTS capability")