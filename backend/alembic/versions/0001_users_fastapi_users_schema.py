"""users table schema for FastAPI Users

Revision ID: 0001
Revises:
Create Date: 2026-07-28

注意：本迁移使用原生 SQL + IF [NOT] EXISTS，全部声明幂等且不依赖 alembic 事务包装。
原因是 PostgreSQL 不允许在事务 aborted 后继续执行 DDL，且某些 DDL（如 BOOLEAN cast）
会因列默认值而失败；使用 IF EXISTS 让我们可以从半成功状态恢复。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. 确保 users 表存在（兜底 CREATE TABLE IF NOT EXISTS）
    #    此前该表由 init_users() 在 pg_schema.py 中创建，ae3e618 refactor
    #    将 DDL 迁至 Alembic；新部署/重建库需要此 CREATE 兜底。
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'user',
            email TEXT DEFAULT '',
            hashed_password TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            phone VARCHAR(20),
            token_version INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")
    # DROP legacy unique constraint on username (FastAPI Users doesn't use it)
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    # Remove the old password_hash column if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='password_hash'
            ) THEN
                ALTER TABLE users RENAME COLUMN password_hash TO hashed_password;
            END IF;
        END$$;
    """)

    # 1. 加新列（幂等 DDL，符合 One-shot 规则的可重复声明）
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0")

    # 2. is_active INTEGER -> BOOLEAN（处理 DEFAULT 1 的 cast 冲突）
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE BOOLEAN USING is_active::boolean")
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE")

    # 3. email 加 NOT NULL + 唯一约束
    #    旧库可能存在多行 email=''，先把空 email 用 id 区分开
    op.execute(
        "UPDATE users SET email = 'legacy_' || id || '@placeholder.local' "
        "WHERE email IS NULL OR email = ''"
    )
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # 4. username 放宽为可空（降级为显示名）+ 删旧唯一约束
    op.execute("ALTER TABLE users ALTER COLUMN username DROP NOT NULL")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
    op.execute("ALTER TABLE users ALTER COLUMN username SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE INTEGER USING is_active::int")
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT 1")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_verified")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_superuser")