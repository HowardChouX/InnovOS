"""用户 Pydantic schemas - 基于 FastAPI Users BaseUser。"""
from fastapi_users import schemas
from pydantic import Field


class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。"""
    username: str | None = None
    phone: str | None = None
    role: str = "user"


class UserCreate(schemas.BaseUserCreate):
    """用户创建 schema。email + password 必填，phone 可选。"""
    username: str | None = None
    phone: str = Field(default=None, description="手机号，仅档案存储")


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新 schema。"""
    username: str | None = None
    phone: str | None = None