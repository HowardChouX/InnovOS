"""merge: 9005 + 0016 -> single head

Revision ID: 9006
Revises: 9005, 0016
Create Date: 2026-07-30

合并最终分支：models 表 + 所有其他表归并到 single head。
"""
from alembic import op

revision = "9006"
down_revision = ("9005", "0016")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
