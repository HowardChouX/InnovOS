"""认证 schemas 测试。"""
import pytest
from pydantic import ValidationError

from app.auth.schemas import UserCreate, UserRead, UserUpdate


def test_user_create_has_email_password_phone():
    """UserCreate 必须包含 phone, password, email 字段。"""
    u = UserCreate(
        email="test@example.com",
        password="test1234",
        phone="13800000000",
    )
    assert u.email == "test@example.com"
    assert u.password == "test1234"
    assert u.phone == "13800000000"


def test_user_create_email_optional():
    """email 可选，phone 必填。"""
    u = UserCreate(phone="13800000000", password="test1234")
    assert u.email is None
    assert u.phone == "13800000000"


def test_user_read_has_role():
    """UserRead 包含 role 和 phone 字段。"""
    u = UserRead(
        id=1, phone="13800000000", email="test@example.com", is_active=True,
        is_superuser=False, is_verified=False, role="user",
    )
    assert u.role == "user"
    assert u.phone == "13800000000"


def test_user_read_phone_required():
    """UserRead 的 phone 必填。"""
    with pytest.raises(ValidationError):
        UserRead(
            id=1, email="test@example.com", is_active=True,
            is_superuser=False, is_verified=False, role="user",
        )


def test_user_update_all_fields_optional():
    """UserUpdate 无参调用必须成功（username/phone/email 均可选）。"""
    u = UserUpdate()
    assert u.username is None
    assert u.phone is None
    assert u.email is None


def test_user_update_phone_validation():
    """UserUpdate.phone 有格式校验，且允许 None。"""
    u = UserUpdate(phone="13800000000")
    assert u.phone == "13800000000"

    u = UserUpdate(phone=None)
    assert u.phone is None

    with pytest.raises(ValidationError):
        UserUpdate(phone="abc")

    with pytest.raises(ValidationError):
        UserUpdate(phone="1380000000")
