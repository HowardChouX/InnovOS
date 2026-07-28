"""FastAPI Users 异常 -> 中文错误信息映射。"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_users import exceptions as fu_exceptions

EXCEPTION_MAP: dict[type, tuple[int, str | None]] = {
    fu_exceptions.UserAlreadyExists: (400, "该邮箱已注册"),
    fu_exceptions.InvalidID: (400, "无效的用户 ID"),
    fu_exceptions.UserNotExists: (404, "用户不存在"),
    fu_exceptions.UserInactive: (400, "用户已被禁用"),
    fu_exceptions.UserAlreadyVerified: (400, "用户已验证"),
    fu_exceptions.InvalidVerifyToken: (400, "无效的验证链接"),
    fu_exceptions.InvalidResetPasswordToken: (400, "无效的重置链接"),
    fu_exceptions.InvalidPasswordException: (400, None),  # 用 reason
}


async def fastapi_users_exception_handler(request: Request, exc: Exception):
    """统一处理 FastAPI Users 异常，返回中文错误信息。"""
    for exc_type, (status, msg) in EXCEPTION_MAP.items():
        if isinstance(exc, exc_type):
            if msg is None:
                msg = getattr(exc, "reason", "密码不符合要求")
            return JSONResponse(status_code=status, content={"detail": msg})
    return JSONResponse(status_code=400, content={"detail": "认证错误"})