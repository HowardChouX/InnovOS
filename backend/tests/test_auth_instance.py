"""FastAPIUsers 实例测试。"""
from app.auth.instance import current_active_user, current_superuser, fastapi_users


def test_fastapi_users_instance():
    """fastapi_users 实例存在。"""
    assert fastapi_users is not None


def test_current_active_user_dependency():
    """current_active_user 是可调用的依赖。"""
    assert callable(current_active_user)


def test_current_superuser_dependency():
    """current_superuser 是可调用的依赖。"""
    assert callable(current_superuser)