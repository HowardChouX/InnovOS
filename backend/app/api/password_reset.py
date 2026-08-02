# app/api/password_reset.py
"""密码重置路由 — 短信 OTP 版（替代原邮箱 OTP 版）。

- POST /send-code：向手机号下发短信验证码（阿里云模板 100003）。
  不查询用户 —— 未知手机号同样下发并返回 202（防探测，不暴露注册状态）。
- POST /verify：核验短信验证码后更新密码（复用 UserManager 的 bcrypt 哈希逻辑）。

限流：复用 app/rate_limit_redis.py 中的 sms_otp_* 限流器实例。
导入期即共享同一实例，短信发送/核验配额在 sms-verification 与
password-reset 两条链路上共用。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_users.manager import BaseUserManager
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rate_limit_redis import (
    sms_otp_ip_limiter,
    sms_otp_request_limiter,
    sms_otp_verify_limiter,
)
from app.auth.users import get_user_manager
from app.core.config import settings
from app.db.models import User
from app.db.session import get_session
from app.exceptions.sms_verification import SmsRateLimited, SmsSendFailed
from app.schemas.sms_verification import SmsSendOut
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


class PasswordResetSendIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")


class PasswordResetVerifyIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/send-code", response_model=SmsSendOut, status_code=202)
async def send_reset_code(payload: PasswordResetSendIn, request: Request) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 防探测：不查询用户，未知手机号同样下发验证码并返回 202
    result = await sms_client.send_code(payload.phone, settings.SMS_RESET_PASSWORD_TEMPLATE_CODE)
    if not result["success"]:
        raise SmsSendFailed()
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", status_code=200)
async def verify_reset_code(
    payload: PasswordResetVerifyIn,
    request: Request,
    session: Session = Depends(get_session),
    user_manager: BaseUserManager = Depends(get_user_manager),
) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 1. 核验短信验证码
    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "RESET_CODE_INVALID", "reason": "验证码错误"},
        )

    # 2. 查找用户（与 user_manager 共用同一 ORM session）
    user = session.execute(
        select(User).where(User.phone == payload.phone)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "reason": "用户不存在"},
        )

    # 3. 禁止与旧密码相同（password_helper 复用 pwdlib 校验）
    same_password, _ = user_manager.password_helper.verify_and_update(
        payload.new_password, user.hashed_password,
    )
    if same_password:
        raise HTTPException(
            status_code=400,
            detail={"code": "SAME_PASSWORD", "reason": "新密码不能与旧密码相同"},
        )

    # 4. 更新密码：fastapi_users 内部校验密码规则并走 password_helper.hash（bcrypt）
    await user_manager._update(user, {"password": payload.new_password})

    return {"reset": True}
