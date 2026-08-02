"""自定义验证码登录路由 - 手机号 + 短信验证码。

核验通过后签发 JWT（与 FastAPI Users 登录同一条链路：strategy.write_token +
transport cookie 配置），Set-Cookie 写入浏览器。未验证的注册用户在登录时
自动激活 is_verified；管理员禁用的用户（is_active=False）拒绝登录。
"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_users.authentication import CookieTransport
from fastapi_users.manager import BaseUserManager
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.users import get_user_manager
from app.auth.schemas import UserRead
from app.db.models import User
from app.db.session import get_session
from app.exceptions.sms_verification import SmsRateLimited
from app.rate_limit_redis import sms_otp_verify_limiter
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


class PhoneCodeLoginIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/login/code", response_model=UserRead)
async def login_with_code(
    payload: PhoneCodeLoginIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    """验证码登录：核验短信验证码，成功后签发 JWT 并 Set-Cookie。"""
    # 验证码登录专属限流：每个手机号 60s 最多 10 次核验。
    # 复用 sms_otp_verify_limiter —— 与 sms-verifications/verify、password-reset/verify
    # 共用同一按手机号的验证预算，避免攻击者借多条链路分别爆破。
    # IP 维度已由全局 api_limiter 中间件覆盖（120/min）。
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_CODE_INVALID", "reason": "验证码错误"},
        )

    # 查找用户
    user = session.execute(select(User).where(User.phone == payload.phone)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_USER_NOT_FOUND", "reason": "该手机号未注册"},
        )
    # 管理员禁用（is_active=False）的用户拒绝登录 —— 不得借验证码自行重新激活
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail={"code": "LOGIN_USER_DISABLED", "reason": "该账号已被禁用"},
        )
    # 未验证的注册用户 → 仅翻转 is_verified（is_active 不动，只有管理员可改）
    if not user.is_verified:
        user.is_verified = True
        session.commit()

    # 签发 JWT（auth_backend.get_strategy 即 get_jwt_strategy，同一密钥/audience）
    token = await get_jwt_strategy().write_token(user)
    await user_manager.on_after_login(user, request, response)

    # Set-Cookie：沿用 transport 配置（开发 token / 生产 __Host-token）
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
    return UserRead.model_validate(user)
