"""merge: 9004 + 0015 -> single branch

Revision ID: 9005
Revises: 9004, 0015
Create Date: 2026-07-30

合并含 system_settings 的分支。
"""
from alembic import op

revision = "9005"
down_revision = ("9004", "0015")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
