"""rename users.password_hash -> users.hashed_password（FastAPI Users 期望的列名）

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-29

幂等：仅在 password_hash 列存在且 hashed_password 不存在时执行。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用条件 SQL：只有当 password_hash 存在且 hashed_password 不存在时才 RENAME
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='password_hash'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='hashed_password'
            ) THEN
                ALTER TABLE users RENAME COLUMN password_hash TO hashed_password;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='hashed_password'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='password_hash'
            ) THEN
                ALTER TABLE users RENAME COLUMN hashed_password TO password_hash;
            END IF;
        END$$;
    """)
