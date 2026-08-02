"""video_tasks 表 DDL 测试 — 验证 init_video_tasks 发出预期 SQL。"""
from unittest.mock import MagicMock

from app.tables.pg_schema import init_video_tasks


def test_init_video_tasks_creates_table_and_indexes():
    db = MagicMock()
    init_video_tasks(db)

    sqls = [call.args[0] for call in db.execute.call_args_list]
    joined = "\n".join(sqls)

    assert "CREATE TABLE IF NOT EXISTS video_tasks" in joined
    assert "remote_task_id" in joined
    assert "video_url" in joined
    # 两个索引
    assert "idx_video_tasks_user" in joined
    assert "idx_video_tasks_status" in joined
