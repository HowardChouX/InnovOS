"""用户 Pydantic schemas - 基于 FastAPI Users BaseUser。"""

from fastapi_users import schemas
from pydantic import EmailStr, Field


class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。email 可选（phone-first，仅通知用）。"""

    username: str | None = None
    phone: str
    email: EmailStr | None = None


class UserCreate(schemas.BaseUserCreate):
    """用户创建 schema。phone + password 必填，email 可选。"""

    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    # EmailStr：提供时校验格式，避免非法 email 入库后 UserRead 响应校验 500
    email: EmailStr | None = None
    username: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新 schema。"""

    username: str | None = None
    phone: str | None = Field(default=None, min_length=11, max_length=11, pattern=r"^1\d{10}$")
    email: str | None = None
