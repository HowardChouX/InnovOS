"""phone as primary login identifier, email nullable, drop email_verifications

Revision ID: 0019
Revises: 9007
Create Date: 2026-08-01

认证体系从邮箱 OTP 切换到阿里云短信验证码：
- phone 升为主登录标识：NOT NULL + UNIQUE + 索引
- email 降级为通知渠道：可空（保留唯一索引，允许多个 NULL）
- 删除 email_verifications 表（验证码生命周期改由阿里云托管）

全部使用原生 SQL + IF [NOT] EXISTS，幂等且不依赖事务包装（与 0001 一致）。
开发阶段无真实用户；对历史无 phone 的行用 id 生成占位号以避免唯一约束冲突。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "9007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. phone 回填占位号（历史行可能无 phone），避免 NOT NULL/UNIQUE 冲突
    op.execute(
        "UPDATE users SET phone = 'legacy_' || id WHERE phone IS NULL OR phone = ''"
    )
    # 2. phone NOT NULL + 唯一索引
    op.execute("ALTER TABLE users ALTER COLUMN phone SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)")

    # 3. email 降级为可空（通知用）；唯一索引保留（PG 允许多个 NULL）
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")

    # 4. 删除 email_verifications 表（含索引，CASCADE 无外部依赖）
    op.execute("DROP TABLE IF EXISTS email_verifications")


def downgrade() -> None:
    # 恢复 email NOT NULL（空值回填占位邮箱）
    op.execute(
        "UPDATE users SET email = 'legacy_' || id || '@placeholder.local' "
        "WHERE email IS NULL OR email = ''"
    )
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")

    # phone 改回可空，删唯一索引
    op.execute("DROP INDEX IF EXISTS ix_users_phone")
    op.execute("ALTER TABLE users ALTER COLUMN phone DROP NOT NULL")

    # 重建 email_verifications 表（与 0006a 一致）
    op.execute("""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            code_hash CHAR(64) NOT NULL,
            attempts SMALLINT NOT NULL DEFAULT 0,
            max_attempts SMALLINT NOT NULL DEFAULT 5,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            purpose VARCHAR(32) NOT NULL DEFAULT 'email_verification',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_user_id_idx "
        "ON email_verifications(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_email_idx "
        "ON email_verifications(email)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_active_idx "
        "ON email_verifications(consumed_at) WHERE consumed_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx "
        "ON email_verifications(email, purpose)"
    )
