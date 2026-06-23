"""initial_schema

Revisions ID: 387ddce168a7
Revises:
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "387ddce168a7"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables by running pg_schema's init logic."""
    from app.tables.pg_schema import init_all_tables
    from app.database import get_db

    db = get_db()
    try:
        init_all_tables(db)
        db.commit()
    finally:
        db.close()


def downgrade() -> None:
    """Drop all tables (reverse of upgrade)."""
    tables = [
        "audit_log", "knowledge_vectors", "knowledge_docs",
        "knowledge_items", "knowledge_bases", "knowledge_groups",
        "models", "evaluations", "feedbacks", "workflows",
        "workflow_steps", "solutions", "analyses", "tasks",
        "patent_vectors", "patents", "notifications",
        "api_keys", "model_providers", "users",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
