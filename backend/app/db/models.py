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

    # 覆盖 FastAPI Users 的 email 字段：改为可空，仅通知用
    email: Mapped[str | None] = mapped_column(
        String(320), nullable=True, unique=True
    )

    # 手机号：主登录标识
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )

    # InnovOS 扩展字段
    username = Column(String(100), nullable=True)   # 显示名，可空
    token_version = Column(Integer, default=0)       # 撤销机制
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())