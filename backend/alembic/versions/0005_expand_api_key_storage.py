"""expand api_keys to encrypted storage + add model_providers audit columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-29

扩展 api_keys 表:
- 增加 AES-256-GCM 密文列(key_ciphertext BYTEA / key_nonce 12 bytes)
- 增加 HMAC fingerprint / prefix / suffix 字段
- 增加 priority / is_active / max_rpm 轮询配置
- 增加 lease_count / success_count / failure_count / cooldown_until 运行时指标
- 增加 created_by / updated_by 审计列
- 增加选择索引 ix_api_keys_selection(provider_id, priority, cooldown_until, lease_count, id)
- 显式 DROP 旧 plaintext 列(api_key / api_base_url / api_model / current_rpm / key_name / last_reset_at)

扩展 model_providers 表:
- 增加 created_by / updated_by 审计列
- 显式 DROP 旧 Key 与运行时统计列(api_key_encrypted / current_rpm / request_count / last_used_at / last_reset_at / priority)

注意:旧数据已被 init_all_tables() 在启动时 TRUNCATE 清除,本迁移只负责升级 schema 形态,
不负责数据迁移。新数据由管理员通过 Web UI 录入。

若数据库非空且有遗留 Provider/Key 数据,迁移前应:
  1. 备份 pg_dump
  2. 手动 TRUNCATE model_providers / api_keys
  3. 再执行本迁移
"""
from alembic import op

revision = "0005a"
down_revision = "0005b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── api_keys: 完整重建(新结构与旧 plaintext 结构不兼容) ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys_new (
            id BIGSERIAL PRIMARY KEY,
            provider_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_ciphertext     BYTEA NOT NULL,
            key_nonce          BYTEA NOT NULL,
            encryption_version SMALLINT NOT NULL DEFAULT 1,
            key_fingerprint    BYTEA NOT NULL,
            key_prefix         VARCHAR(12),
            key_suffix         VARCHAR(8),
            priority  INTEGER NOT NULL DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            max_rpm   INTEGER,
            lease_count   BIGINT NOT NULL DEFAULT 0,
            request_count BIGINT NOT NULL DEFAULT 0,
            success_count BIGINT NOT NULL DEFAULT 0,
            failure_count BIGINT NOT NULL DEFAULT 0,
            last_used_at    TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            cooldown_until  TIMESTAMPTZ,
            last_error_code VARCHAR(64),
            created_by BIGINT,
            updated_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_api_keys_nonce_length
                CHECK (OCTET_LENGTH(key_nonce) = 12),
            CONSTRAINT ck_api_keys_fingerprint_len
                CHECK (OCTET_LENGTH(key_fingerprint) = 32),
            CONSTRAINT ck_api_keys_name_not_blank
                CHECK (BTRIM(name) <> ''),
            CONSTRAINT ck_api_keys_encryption_version
                CHECK (encryption_version >= 1)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_selection
        ON api_keys_new (provider_id, priority, cooldown_until, lease_count, id)
        WHERE is_active = TRUE;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_provider_active
        ON api_keys_new (provider_id, is_active);
    """)
    # DROP 旧 api_keys 表(其 plaintext 数据已无意义)
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE")
    op.execute("ALTER TABLE api_keys_new RENAME TO api_keys")
    # 重建原索引名
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_selection
        ON api_keys (provider_id, priority, cooldown_until, lease_count, id)
        WHERE is_active = TRUE;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_provider_active
        ON api_keys (provider_id, is_active);
    """)

    # ── model_providers: 增加审计列,DROP 旧 Key / 统计列 ──
    op.execute("""
        ALTER TABLE model_providers
            ADD COLUMN IF NOT EXISTS created_by BIGINT,
            ADD COLUMN IF NOT EXISTS updated_by BIGINT
    """)
    for legacy_col in (
        "api_key_encrypted",
        "current_rpm",
        "request_count",
        "last_used_at",
        "last_reset_at",
        "priority",
    ):
        op.execute(f"ALTER TABLE model_providers DROP COLUMN IF EXISTS {legacy_col}")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_model_providers_enabled
        ON model_providers (provider_id) WHERE is_enabled = 1
    """)


def downgrade() -> None:
    # 不提供自动恢复旧明文结构;需手动从备份还原
    raise RuntimeError(
        "0005_downgrade not supported. Restore from pre-migration backup if needed."
    )