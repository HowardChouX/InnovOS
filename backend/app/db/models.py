"""User ORM 模型 - 基于 FastAPI Users 的 SQLAlchemyBaseUserTable。"""
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    """用户表 ORM 模型。

    SQLAlchemyBaseUserTable 提供: email, hashed_password,
    is_active, is_superuser, is_verified
    手动添加: id (INTEGER PK)
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # InnovOS 扩展字段
    username = Column(String(100), nullable=True)   # 显示名，可空
    phone = Column(String(20), nullable=True)        # 档案字段，不参与登录
    role = Column(String(20), default="user")        # 业务角色
    token_version = Column(Integer, default=0)       # 撤销机制
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())