"""add purpose to email_verifications

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-30

为 email_verifications 表加 purpose 列,用于区分注册验证 (email_verification)
与重置密码 (password_reset) 两条 OTP 流。默认值为 email_verification,保证既有
注册流程行为不变;新增复合索引 (email, purpose) 加速按业务目的的查表。

纯 schema 声明,幂等,可重跑(IF NOT EXISTS)。
"""
from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE email_verifications "
        "ADD COLUMN IF NOT EXISTS purpose VARCHAR(32) NOT NULL "
        "DEFAULT 'email_verification'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx "
        "ON email_verifications(email, purpose)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS email_verifications_email_purpose_idx")
    op.execute("ALTER TABLE email_verifications DROP COLUMN IF EXISTS purpose")
