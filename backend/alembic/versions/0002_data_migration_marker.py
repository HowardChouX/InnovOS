"""data migration marker - 运行 migrate_users_to_fastapi_users.py 后应用此 revision

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28
"""
from typing import Sequence, Union

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空 revision - 仅作为 data migration 完成的版本锚点。"""
    pass


def downgrade() -> None:
    pass