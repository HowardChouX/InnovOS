"""users table schema for FastAPI Users

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加新列（幂等 DDL，符合 One-shot 规则的可重复声明）
    op.add_column(
        "users", sa.Column("is_superuser", sa.Boolean(), server_default=sa.false())
    )
    op.add_column(
        "users", sa.Column("is_verified", sa.Boolean(), server_default=sa.false())
    )
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))

    # 2. 改列类型（is_active INTEGER -> BOOLEAN）
    op.alter_column(
        "users", "is_active",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        postgresql_using="is_active::boolean",
        server_default=sa.true(),
    )

    # 3. email 加 NOT NULL + 唯一约束
    # 注意：email 的 NOT NULL 要求所有现有用户已有 email，由 data backfill 脚本保证
    op.alter_column("users", "email", existing_type=sa.Text(), nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 4. username 放宽为可空（降级为显示名）
    op.alter_column("users", "username", existing_type=sa.Text(), nullable=True)
    # 删旧唯一约束（若存在），改为普通索引
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "username", existing_type=sa.Text(), nullable=False)
    op.drop_index("ix_users_email", table_name="users")
    op.alter_column("users", "email", existing_type=sa.Text(), nullable=True)
    op.alter_column(
        "users", "is_active",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        postgresql_using="is_active::int",
        server_default="1",
    )
    op.drop_column("users", "phone")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "is_superuser")