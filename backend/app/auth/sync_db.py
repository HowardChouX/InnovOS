"""同步 SQLAlchemy UserDatabase adapter - 适配 InnovOS 的同步 SQLAlchemy。"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class SyncSQLAlchemyUserDatabase:
    """为同步 Session 实现的 UserDatabase。

    实现 FastAPI Users 的 BaseUserDatabase 接口（get/get_by_email/create/update/delete），
    使用同步 SQLAlchemy 而非 AsyncSession。
    """

    def __init__(self, session: Session, user_table: type[User]):
        self.session = session
        self.user_table = user_table

    async def get(self, id: int) -> User | None:
        return self.session.get(User, id)

    async def get_by_email(self, email: str) -> User | None:
        # phone-first：email 为可选通知字段。email=None 时返回 None，
        # 避免 `User.email == None` 生成 `IS NULL` 误匹配所有无邮箱用户
        # （BaseUserManager.create 的唯一性前置检查依赖此行为）。
        if not email:
            return None
        statement = select(User).where(User.email == email)
        return self.session.execute(statement).scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """按手机号查找（主登录标识）。"""
        statement = select(User).where(User.phone == phone)
        return self.session.execute(statement).scalar_one_or_none()

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> User | None:
        raise NotImplementedError("OAuth not supported yet")

    async def create(self, create_dict: dict[str, Any]) -> User:
        user = User(**create_dict)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.commit()