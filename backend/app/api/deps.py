"""
FastAPI dependencies - 兼容垫片。

- SessionDep: 业务表用 psycopg2（保持不变）
- CurrentUser/SuperUserDep: 指向 FastAPI Users 依赖（认证用）

注意：deps.py 中旧的 get_current_user/get_current_superuser 函数（基于 psycopg2 + JWT）
已被 FastAPI Users 替代，保留为仅做向后兼容垫片，业务路由将逐步迁移。
"""
from typing import Annotated, Any

from fastapi import Depends

from app.auth.instance import current_active_user, current_superuser
from app.database import get_db_dep

# 业务表仍用 psycopg2
SessionDep = Annotated[Any, Depends(get_db_dep)]

# 认证依赖（别名）
CurrentUser = current_active_user
SuperUserDep = current_superuser