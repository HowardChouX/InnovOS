"""merge: 9003 + 0014 -> single branch

Revision ID: 9004
Revises: 9003, 0014
Create Date: 2026-07-30

合并含 knowledge_vectors 的分支。
"""
from alembic import op

revision = "9004"
down_revision = ("9003", "0014")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
