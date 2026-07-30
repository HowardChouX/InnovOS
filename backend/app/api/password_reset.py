# app/api/password_reset.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.email_verification import (
    EmailNotFound,
    EmailVerificationError,
    OtpRateLimited,
)
from app.rate_limit_redis import (
    email_otp_ip_limiter,
    email_otp_request_limiter,
    email_otp_verify_limiter,
)
from app.schemas.email_verification import (
    OtpIssuedOut,
    OtpRequestIn,
    OtpResendIn,
    OtpVerifyIn,
    ResetPasswordSetIn,
)
from app.services.email_verification_service import (
    EmailVerificationService,
    OtpPurpose,
)

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


@router.post("/request-otp", response_model=OtpIssuedOut, status_code=202)
def request_otp(payload: OtpRequestIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.check(ip)[0]:
        raise OtpRateLimited(60)
    if not email_otp_request_limiter.check(payload.email)[0]:
        raise OtpRateLimited(60)
    try:
        rec = EmailVerificationService().resend(
            payload.email, request, purpose=OtpPurpose.PASSWORD_RESET,
        )
    except EmailNotFound:
        # 防探测：未知邮箱静默返回 202
        return OtpIssuedOut(
            expires_in=settings.OTP_TTL_SECONDS,
            next_resend_in=settings.OTP_RESEND_COOLDOWN,
        )
    except EmailVerificationError:
        return OtpIssuedOut(
            expires_in=settings.OTP_TTL_SECONDS,
            next_resend_in=settings.OTP_RESEND_COOLDOWN,
        )
    return OtpIssuedOut(**rec)


@router.post("/resend-otp", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    allowed, _, _ = email_otp_ip_limiter.check(ip)
    if not allowed:
        raise OtpRateLimited(60)
    rec = EmailVerificationService().resend(
        payload.email, request, purpose=OtpPurpose.PASSWORD_RESET,
    )
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=dict)
def verify_otp(payload: OtpVerifyIn, request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.check(ip)[0]:
        raise OtpRateLimited(60)
    if not email_otp_verify_limiter.check(payload.email)[0]:
        raise OtpRateLimited(60)
    rec = EmailVerificationService().verify(
        payload.email, payload.code, request, purpose=OtpPurpose.PASSWORD_RESET,
    )
    return rec


@router.post("/set-password", status_code=200)
def set_password(payload: ResetPasswordSetIn, request: Request) -> dict:
    EmailVerificationService().set_password_with_session(
        payload.reset_token, payload.new_password,
    )
    return {"reset": True}
