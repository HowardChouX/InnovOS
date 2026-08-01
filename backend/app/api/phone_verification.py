# app/api/phone_verification.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.sms_verification import SmsRateLimited
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
async def send_sms(payload: SmsSendIn, request: Request) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    template_code = (
        settings.SMS_RESET_PASSWORD_TEMPLATE_CODE
        if payload.purpose == "password_reset"
        else settings.SMS_REGISTER_TEMPLATE_CODE
    )
    await sms_client.send_code(payload.phone, template_code)
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", response_model=SmsVerifyOut)
async def verify_sms(payload: SmsVerifyIn, request: Request) -> SmsVerifyOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        return SmsVerifyOut(verified=False, already=False)

    # 注册验证：翻 is_verified + is_active
    if payload.purpose == "register":
        from app.database import db_session

        with db_session() as db:
            db.execute(
                "UPDATE users SET is_verified=TRUE, is_active=TRUE WHERE phone=%s AND is_verified=FALSE",
                (payload.phone,),
            )
    return SmsVerifyOut(verified=True, already=False)
