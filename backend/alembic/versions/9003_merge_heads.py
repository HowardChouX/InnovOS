"""merge: 9002 + 0013 -> single branch

Revision ID: 9003
Revises: 9002, 0013
Create Date: 2026-07-30

合并含 knowledge_docs / knowledge_jobs 的分支。
"""
from alembic import op

revision = "9003"
down_revision = ("9002", "0013")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
