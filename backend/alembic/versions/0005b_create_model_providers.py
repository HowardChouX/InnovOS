"""create model_providers table

Revision ID: 0005b
Revises: 0004
Create Date: 2026-07-30

供应商聚合根表：Provider 端点配置(Host、协议、模型列表、启用状态)。
Key 不在此表存储(在 api_keys 表 AES-256-GCM 加密保存)。
含审计列 created_by / updated_by；含按 is_enabled 的部分索引。
本迁移同时 DROP 旧 plaintext 列（api_key_encrypted 等），保持 schema 形态稳定。
"""
from alembic import op

revision = "0005b"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 主表 ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_providers (
            id SERIAL PRIMARY KEY,
            provider_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            protocol TEXT DEFAULT 'openai',
            api_host TEXT NOT NULL,
            api_model TEXT DEFAULT '',
            models TEXT DEFAULT '[]',
            max_rpm INTEGER DEFAULT 60,
            is_enabled INTEGER DEFAULT 1,
            created_by BIGINT,
            updated_by BIGINT,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)

    # ── 按 is_enabled 的部分索引 ──
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_model_providers_enabled
        ON model_providers (provider_id) WHERE is_enabled = 1;
    """)

    # ── 兼容旧字段(已废弃,DROP COLUMN IF EXISTS 幂等) ──
    for legacy_col in (
        "api_key_encrypted",
        "current_rpm",
        "request_count",
        "last_used_at",
        "last_reset_at",
        "priority",
    ):
        op.execute(f"ALTER TABLE model_providers DROP COLUMN IF EXISTS {legacy_col}")


def downgrade() -> None:
    # DROP 索引与表即可。legacy 列如存在会随表一起 DROP。
    op.execute("DROP INDEX IF EXISTS ix_model_providers_enabled")
    op.execute("DROP TABLE IF EXISTS model_providers")