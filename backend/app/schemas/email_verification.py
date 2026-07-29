# app/schemas/email_verification.py
from pydantic import BaseModel, EmailStr, Field


class OtpRequestIn(BaseModel):
    email: EmailStr


class OtpResendIn(BaseModel):
    email: EmailStr


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpIssuedOut(BaseModel):
    expires_in: int
    next_resend_in: int = 60


class OtpVerifiedOut(BaseModel):
    verified: bool
    already: bool = False
