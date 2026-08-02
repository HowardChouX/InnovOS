# app/schemas/sms_verification.py
from pydantic import BaseModel, Field

from app.auth.schemas import UserRead


class SmsSendIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    purpose: str = "register"  # register | password_reset


class SmsVerifyIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: str = "register"


class SmsSendOut(BaseModel):
    expires_in: int = 300
    next_resend_in: int = 60


class SmsVerifyOut(BaseModel):
    verified: bool
    already: bool = False
    # 注册验证通过时随响应返回用户并自动登录（Set-Cookie），前端无需再跳登录页
    user: UserRead | None = None
