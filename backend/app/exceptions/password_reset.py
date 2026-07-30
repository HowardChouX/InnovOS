# app/exceptions/password_reset.py
from app.exceptions.email_verification import EmailVerificationError


class InvalidResetSession(EmailVerificationError):
    """reset_session_token 无效、过期、已消费或 audience 错。"""
    def __init__(self) -> None:
        super().__init__(
            401, "RESET_SESSION_INVALID", "重置会话无效或已过期,请重新获取验证码"
        )


class WeakPassword(EmailVerificationError):
    """新密码不符合强度要求。"""
    def __init__(self, reason: str) -> None:
        super().__init__(
            400, "WEAK_PASSWORD", reason, {"reason": reason}
        )