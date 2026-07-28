"""FastAPIUsers 实例与依赖工厂。"""
from fastapi_users import FastAPIUsers

from app.auth.backend import auth_backend
from app.auth.users import get_user_manager
from app.db.models import User

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

# 依赖：当前活跃用户
current_active_user = fastapi_users.current_user(active=True)
# 依赖：当前超级用户
current_superuser = fastapi_users.current_user(active=True, superuser=True)