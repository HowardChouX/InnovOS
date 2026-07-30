"""merge: 0005a + 0008 -> single branch

Revision ID: 9001
Revises: 0005a, 0008
Create Date: 2026-07-30

合并 alembic 多头分支。将以下两个 head 合并到一条路径：
- 0005a: api_keys 重建
- 0008:  audit_log

本文件为空迁移，仅用于拓扑收敛，让 alembic 能在单进程内完成 upgrade heads。
"""
from alembic import op

revision = "9001"
down_revision = ("0005a", "0008")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
