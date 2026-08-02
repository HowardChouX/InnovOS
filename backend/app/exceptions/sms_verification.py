# app/exceptions/sms_verification.py
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class SmsVerificationError(Exception):
    status: int
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class SmsSendFailed(SmsVerificationError):
    def __init__(self) -> None:
        super().__init__(503, "SMS_SEND_FAILED", "短信发送失败，请稍后重试")


class SmsVerifyFailed(SmsVerificationError):
    def __init__(self, remaining: int | None = None) -> None:
        detail = {"remaining": remaining} if remaining else None
        super().__init__(400, "SMS_VERIFY_FAILED", "验证码错误", detail)


class SmsRateLimited(SmsVerificationError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(429, "SMS_RATE_LIMITED", "操作过于频繁，请稍后再试", {"retry_after": retry_after})


class SmsPhoneNotFound(SmsVerificationError):
    def __init__(self) -> None:
        super().__init__(404, "PHONE_NOT_FOUND", "该手机号未注册")


async def sms_verification_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, SmsVerificationError):
        return JSONResponse(status_code=500, content={"code": "INTERNAL", "message": "服务异常", "reason": "服务异常"})
    # reason 与 message 同值：reason 是全站统一的用户可见中文错误字段（{code, reason} 契约），
    # message 保留以向后兼容既有调用方。
    body: dict[str, Any] = {"code": exc.code, "message": exc.message, "reason": exc.message}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)
