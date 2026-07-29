# app/api/email_verification.py
from fastapi import APIRouter

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
    except Exception:
        # 防探测：未知邮箱静默返回 202
        return OtpIssuedOut(expires_in=600, next_resend_in=60)
    return OtpIssuedOut(**rec)


@router.post("/resend", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn) -> OtpIssuedOut:
    rec = email_verification_service.resend(payload.email)
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=OtpVerifiedOut)
def verify_otp(payload: OtpVerifyIn) -> OtpVerifiedOut:
    rec = email_verification_service.verify(payload.email, payload.code)
    return OtpVerifiedOut(**rec)