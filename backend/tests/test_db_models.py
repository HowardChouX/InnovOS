"""ORM 模型测试 - 验证 User 模型结构。"""
import pytest
from sqlalchemy import inspect


def test_user_model_has_required_fields():
    """User 模型必须包含 FastAPI Users 标准字段 + InnovOS 扩展字段。"""
    from app.db.models import User
    mapper = inspect(User)
    columns = {c.key for c in mapper.columns}
    # FastAPI Users 标准字段
    assert "id" in columns
    assert "email" in columns
    assert "hashed_password" in columns
    assert "is_active" in columns
    assert "is_superuser" in columns
    assert "is_verified" in columns
    # InnovOS 扩展字段
    assert "username" in columns
    assert "phone" in columns
    assert "token_version" in columns


def test_user_table_name():
    from app.db.models import User
    assert User.__tablename__ == "users"