"""用户 Pydantic schemas - 基于 FastAPI Users BaseUser。"""
from fastapi_users import schemas
from pydantic import Field


class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。"""
    username: str | None = None
    phone: str
    role: str = "user"


class UserCreate(schemas.BaseUserCreate):
    """用户创建 schema。phone + password 必填，email 可选。"""
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    email: str | None = None
    username: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新 schema。"""
    username: str | None = None
    phone: str | None = Field(default=None, min_length=11, max_length=11, pattern=r"^1\d{10}$")
    email: str | None = None
