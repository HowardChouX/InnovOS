"""自定义密码登录路由 - 手机号 + 密码（替代 fastapi-users 内置 get_auth_router）。

内置路由的 authenticate() 用 get_by_email(username) 查 email 字段，而 InnovOS
以手机号为主登录标识 → 手机号登录永远失败。本路由改为按 phone 查找（回退 email
以兼容历史数据/测试），并返回统一的 {code, reason} 中文错误：

- LOGIN_BAD_CREDENTIALS  手机号或密码错误（含用户不存在/密码错误/被禁用，不区分以免泄露注册状态）
- LOGIN_USER_NOT_VERIFIED 账号未验证（前端据此跳转验证页）

logout 复用 fastapi-users authenticator 的 current_user_token 依赖。
"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication import CookieTransport
from fastapi_users.manager import BaseUserManager
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.instance import fastapi_users
from app.auth.schemas import UserRead
from app.auth.users import get_user_manager
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/api/auth/jwt", tags=["auth"])


@router.post("/login", response_model=UserRead)
async def login(
    request: Request,
    response: Response,
    credentials: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    """密码登录：手机号（或邮箱）+ 密码，成功后签发 JWT 并 Set-Cookie。"""
    identifier = credentials.username
    # 主标识为手机号；回退 email 兼容历史数据与既有测试
    user = session.execute(select(User).where(User.phone == identifier)).scalar_one_or_none()
    if user is None:
        user = session.execute(select(User).where(User.email == identifier)).scalar_one_or_none()

    verified = False
    if user is not None:
        verified, updated_hash = user_manager.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        # 密码哈希算法升级时顺带落库
        if verified and updated_hash is not None:
            user.hashed_password = updated_hash
            session.commit()

    if user is None or not verified or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_BAD_CREDENTIALS", "reason": "手机号或密码错误"},
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_USER_NOT_VERIFIED", "reason": "账号未验证，请先完成手机验证"},
        )

    # 签发 JWT（与验证码登录同一密钥/audience）
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


@router.post("/logout", status_code=204)
async def logout(
    user_token: tuple[User, str] = Depends(fastapi_users.authenticator.current_user_token(active=True)),
):
    """登出：销毁 JWT token（CookieTransport 会清除 cookie）。"""
    user, token = user_token
    return await auth_backend.logout(get_jwt_strategy(), user, token)
