# app/api/phone_verification.py
from typing import cast

from fastapi import APIRouter, Depends, Request, Response
from fastapi_users.authentication import CookieTransport
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.backend import auth_backend, get_jwt_strategy
from app.core.config import settings
from app.db.models import User
from app.db.session import get_session
from app.exceptions.sms_verification import SmsPhoneNotFound, SmsRateLimited, SmsSendFailed
from app.rate_limit_redis import (
    sms_otp_ip_limiter,
    sms_otp_request_limiter,
    sms_otp_verify_limiter,
)
from app.schemas.sms_verification import (
    SmsSendIn,
    SmsSendOut,
    SmsVerifyIn,
    SmsVerifyOut,
)
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth/sms-verifications", tags=["auth"])


@router.post("/send", response_model=SmsSendOut, status_code=202)
async def send_sms(
    payload: SmsSendIn,
    request: Request,
    session: Session = Depends(get_session),
) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 非注册场景（验证码登录）：预检手机号已注册，未注册提示先注册。
    # 注册场景不预检（手机号本就未注册）。
    if payload.purpose != "register":
        exists = session.execute(select(User.id).where(User.phone == payload.phone)).scalar_one_or_none()
        if not exists:
            raise SmsPhoneNotFound()

    template_code = (
        settings.SMS_RESET_PASSWORD_TEMPLATE_CODE
        if payload.purpose == "password_reset"
        else settings.SMS_REGISTER_TEMPLATE_CODE
    )
    result = await sms_client.send_code(payload.phone, template_code)
    if not result["success"]:
        raise SmsSendFailed()

    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", response_model=SmsVerifyOut)
async def verify_sms(
    payload: SmsVerifyIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> SmsVerifyOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        return SmsVerifyOut(verified=False, already=False)

    # 注册验证：翻 is_verified + is_active，并自动登录（用户刚通过短信验证，
    # 与验证码登录同一安全级别），随响应返回用户 + Set-Cookie，省去再跳登录页。
    if payload.purpose == "register":
        user = session.execute(select(User).where(User.phone == payload.phone)).scalar_one_or_none()
        if user is None:
            raise SmsPhoneNotFound()
        user.is_verified = True
        user.is_active = True
        session.commit()
        session.refresh(user)

        token = await get_jwt_strategy().write_token(user)
        transport = cast(CookieTransport, auth_backend.transport)
        response.set_cookie(
            key=transport.cookie_name,
            value=token,
            max_age=transport.cookie_max_age,
            path=transport.cookie_path,
            domain=transport.cookie_domain,
            secure=transport.cookie_secure,
            httponly=transport.cookie_httponly,
            samesite=transport.cookie_samesite,
        )
        from app.auth.schemas import UserRead

        return SmsVerifyOut(verified=True, already=False, user=UserRead.model_validate(user))

    return SmsVerifyOut(verified=True, already=False)
