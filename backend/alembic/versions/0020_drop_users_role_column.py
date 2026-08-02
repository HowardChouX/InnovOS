"""drop users.role column — is_superuser is the sole admin flag

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-02

历史上 users 表同时存在 role('admin'/'user') 与 is_superuser(bool) 两个管理员标识，
分别被 require_admin（判 role）与 SuperUserDep（判 is_superuser）两套闸门读取，
需手动保持一致。本次重构统一为 is_superuser 单一标识，删除冗余的 role 列。

0004 迁移已把历史 role='admin' 回填为 is_superuser=TRUE，数据无丢失风险。
使用原生 SQL + IF EXISTS，幂等且不依赖事务包装（与 0001/0019 一致）。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")


def downgrade() -> None:
    # 恢复列；历史 role 值无法还原，默认 'user'，管理员需手动 is_superuser 已保留
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
    op.execute("UPDATE users SET role = 'admin' WHERE is_superuser = TRUE")
