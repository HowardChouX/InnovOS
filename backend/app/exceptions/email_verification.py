# app/exceptions/email_verification.py
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class EmailVerificationError(Exception):
    status: int
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class EmailNotFound(EmailVerificationError):
    def __init__(self) -> None:
        super().__init__(404, "EMAIL_NOT_FOUND", "该邮箱未注册")


class AlreadyVerified(EmailVerificationError):
    def __init__(self) -> None:
        super().__init__(409, "ALREADY_VERIFIED", "邮箱已验证，请直接登录")


class CodeInvalid(EmailVerificationError):
    def __init__(self, remaining: int) -> None:
        super().__init__(
            400,
            "CODE_INVALID",
            f"验证码错误（剩余 {remaining} 次）",
            {"remaining": remaining},
        )


class CodeExhausted(EmailVerificationError):
    def __init__(self) -> None:
        super().__init__(410, "CODE_EXHAUSTED", "验证码已失效，请重新获取")


class CodeExpired(EmailVerificationError):
    def __init__(self) -> None:
        super().__init__(410, "CODE_EXPIRED", "验证码已过期，请重新获取")


class OtpRateLimited(EmailVerificationError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            429,
            "RATE_LIMITED",
            "操作过于频繁，请稍后再试",
            {"retry_after": retry_after},
        )


class EmailUnavailable(EmailVerificationError):
    def __init__(self) -> None:
        super().__init__(503, "EMAIL_UNAVAILABLE", "邮件服务暂时不可用，请稍后重试")


async def email_verification_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, EmailVerificationError):
        return JSONResponse(status_code=500, content={"code": "INTERNAL", "message": "服务异常"})
    body: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)