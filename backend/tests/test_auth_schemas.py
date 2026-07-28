"""认证 schemas 测试。"""
from app.auth.schemas import UserCreate, UserRead, UserUpdate


def test_user_create_has_email_password_phone():
    """UserCreate 必须包含 email, password, phone 字段。"""
    u = UserCreate(
        email="test@example.com",
        password="test1234",
        phone="13800000000",
    )
    assert u.email == "test@example.com"
    assert u.password == "test1234"
    assert u.phone == "13800000000"


def test_user_create_phone_optional():
    """phone 可选。"""
    u = UserCreate(email="test@example.com", password="test1234")
    assert u.phone is None


def test_user_read_has_role():
    """UserRead 包含 role 字段。"""
    u = UserRead(
        id=1, email="test@example.com", is_active=True,
        is_superuser=False, is_verified=False, role="user",
    )
    assert u.role == "user"