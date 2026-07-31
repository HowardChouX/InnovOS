"""add provider_health, user_model_services, model_call_log + model_providers.notes

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-31

Ops-parity migration. The same DDL lives in `app/tables/pg_schema.py`
and is applied at app boot via `init_all_tables()`. This file exists
so a DBA running `alembic upgrade head` against an existing deployment
sees the same end state.
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT ''")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_health (
            provider_id TEXT PRIMARY KEY
                REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            cooldown_until TIMESTAMPTZ,
            last_error_code VARCHAR(64),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_model_services (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            failover_order INTEGER NOT NULL CHECK (failover_order >= 1),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, provider_id),
            UNIQUE (user_id, failover_order)
        );
    """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_ums_user_enabled ON user_model_services (user_id, is_enabled, failover_order);")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS model_call_log (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            purpose VARCHAR(32) NOT NULL DEFAULT 'chat',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status_code SMALLINT NOT NULL,
            is_success BOOLEAN NOT NULL,
            error_category VARCHAR(32),
            error_message TEXT,
            is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
            failover_from_provider TEXT,
            failover_attempt SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_provider_time ON model_call_log (provider_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_user_time ON model_call_log (user_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_model_time ON model_call_log (model_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_time ON model_call_log (created_at DESC);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mcl_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_model_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_user_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_provider_time")
    op.execute("DROP TABLE IF EXISTS model_call_log")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_enabled")
    op.execute("DROP TABLE IF EXISTS user_model_services")
    op.execute("DROP TABLE IF EXISTS provider_health")
    op.execute("ALTER TABLE model_providers DROP COLUMN IF EXISTS notes")
