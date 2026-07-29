# app/api/email_verification.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.email_verification import EmailVerificationError, OtpRateLimited
from app.rate_limit_redis import email_otp_ip_limiter
from app.schemas.email_verification import (
    OtpIssuedOut,
    OtpRequestIn,
    OtpResendIn,
    OtpVerifyIn,
    OtpVerifiedOut,
)
from app.services.email_verification_service import email_verification_service

router = APIRouter(prefix="/api/auth/email-verifications", tags=["auth"])


@router.post("/request", response_model=OtpIssuedOut, status_code=202)
def request_otp(payload: OtpRequestIn) -> OtpIssuedOut:
    try:
        rec = email_verification_service.resend(payload.email)
    except EmailVerificationError:
        # 防探测：未知邮箱/已验证/冷却中等预期异常静默返回 202
        return OtpIssuedOut(
            expires_in=settings.OTP_TTL_SECONDS,
            next_resend_in=settings.OTP_RESEND_COOLDOWN,
        )
    return OtpIssuedOut(**rec)


@router.post("/resend", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    allowed, _, _ = email_otp_ip_limiter.check(ip)
    if not allowed:
        raise OtpRateLimited(60)
    rec = email_verification_service.resend(payload.email)
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=OtpVerifiedOut)
def verify_otp(payload: OtpVerifyIn, request: Request) -> OtpVerifiedOut:
    ip = request.client.host if request.client else "unknown"
    allowed, _, _ = email_otp_ip_limiter.check(ip)
    if not allowed:
        raise OtpRateLimited(60)
    rec = email_verification_service.verify(payload.email, payload.code)
    return OtpVerifiedOut(**rec)