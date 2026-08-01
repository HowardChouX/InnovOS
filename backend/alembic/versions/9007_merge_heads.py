"""merge: 0018 + 9006 -> single head

Revision ID: 9007
Revises: 0018, 9006
Create Date: 2026-08-01

Merge capability column migration with the existing merge head.
"""
from alembic import op

revision = "9007"
down_revision = ("0018", "9006")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass