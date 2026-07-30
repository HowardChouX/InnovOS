"""create models table

Revision ID: 0016
Revises: 0005b
Create Date: 2026-07-30

models 表 — 独立模型配置（替代 model_providers.models JSON 列）。
逻辑关联 model_providers(provider_id)，不强制 FK。
"""
from alembic import op

revision = "0016"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id SERIAL PRIMARY KEY,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            capabilities TEXT DEFAULT '[]',
            endpoint_types TEXT DEFAULT '[]',
            context_window INTEGER DEFAULT 0,
            max_output_tokens INTEGER DEFAULT 0,
            max_input_tokens INTEGER DEFAULT 0,
            model_group TEXT DEFAULT '',
            is_enabled INTEGER DEFAULT 1,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_models_provider_model "
        "ON models(provider_id, model_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_models_provider_model")
    op.execute("DROP TABLE IF EXISTS models")
