"""FastAPI Users 认证层包 - 过渡期兼容垫片。

旧 app/auth.py 已删除，本垫片从 FastAPI Users 重新导出旧符号
以保持现有 25+ 路由文件继续工作。后续任务会逐步迁移。
"""
from app._legacy_compat import (  # noqa: F401
    _verify_admin_credentials,
    clear_token_cookie,
    create_access_token,
    get_current_user,
    require_admin,
    set_token_cookie,
)
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.database import get_db  # 兼容老测试桩：monkeypatch.setattr("app.auth.get_db", ...)

__all__ = [
    "UserCreate", "UserRead", "UserUpdate",
    "_verify_admin_credentials",
    "clear_token_cookie",
    "create_access_token",
    "get_current_user",
    "require_admin",
    "set_token_cookie",
    "get_db",
]