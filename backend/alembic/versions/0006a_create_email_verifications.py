"""create email_verifications table

Revision ID: 0006a
Revises: 0001
Create Date: 2026-07-30

email_verifications 表 — 6 位邮件 OTP。
注册时落码(code_hash 存 SHA-256 hex)，验证通过后置 consumed_at。
FK 到 users(id) ON DELETE CASCADE。

合并原 0006_add_purpose_to_email_verifications：purpose 列已在初始 CREATE 中包含，
不需要额外 ADD COLUMN 迁移。
"""
from alembic import op

revision = "0006a"
down_revision = "0005a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 主表（purpose 列直接包含，避免后续 ADD COLUMN 迁移）──
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

    # ── 索引 ──
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


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS email_verifications_email_purpose_idx")
    op.execute("DROP INDEX IF EXISTS email_verifications_active_idx")
    op.execute("DROP INDEX IF EXISTS email_verifications_email_idx")
    op.execute("DROP INDEX IF EXISTS email_verifications_user_id_idx")
    op.execute("DROP TABLE IF EXISTS email_verifications")