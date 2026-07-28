"""FastAPI Users 认证层包（过渡期兼容垫片）。

旧 app/auth.py 已重命名为 app/_legacy_auth.py，本包通过 re-export
保持现有 25+ 路由文件继续工作。最终所有引用将迁移到本包内的新模块。
"""
from app._legacy_auth import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    SECRET_KEY as _SECRET_KEY,
    _verify_admin_credentials,
    clear_token_cookie,
    create_access_token,
    get_current_user,
    require_admin,
    set_token_cookie,
)

from app.auth.schemas import UserCreate, UserRead, UserUpdate

__all__ = [
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ACCESS_TOKEN_EXPIRE_HOURS",
    "SECRET_KEY",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "_verify_admin_credentials",
    "clear_token_cookie",
    "create_access_token",
    "get_current_user",
    "require_admin",
    "set_token_cookie",
]