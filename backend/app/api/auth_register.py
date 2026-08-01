"""自定义注册路由 - phone 为唯一登录标识。

替代 fastapi_users.get_register_router 的默认注册端点：
- phone 必填 + 唯一性前置校验（重复 → 400 REGISTER_PHONE_DUPLICATE）
- 创建成功后自动下发短信验证码（阿里云模板 100001）
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_users import exceptions as fui_exceptions
from fastapi_users.manager import BaseUserManager
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.schemas import UserCreate, UserRead
from app.auth.users import get_user_manager
from app.core.config import settings
from app.db.models import User
from app.db.session import get_session
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    """phone + password 注册，成功后自动下发短信验证码。"""
    # 1. 手机号唯一性校验（与 user_manager 共用同一 ORM session）
    existing_id = session.execute(select(User.id).where(User.phone == payload.phone)).scalar_one_or_none()
    if existing_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_PHONE_DUPLICATE", "reason": "该手机号已注册"},
        )

    # 2. 创建用户（safe=True → is_verified=false，is_active 取模型默认值）
    try:
        created_user = await user_manager.create(payload, safe=True, request=request)
    except fui_exceptions.UserAlreadyExists:
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_EMAIL_DUPLICATE", "reason": "该邮箱已注册"},
        ) from None
    except fui_exceptions.InvalidPasswordException as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_INVALID_PASSWORD", "reason": e.reason},
        ) from None
    except IntegrityError:
        # 并发双写兜底：phone 唯一约束拦截，避免 500
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_PHONE_DUPLICATE", "reason": "该手机号已注册"},
        ) from None

    # 3. 自动下发短信验证码（模板 100001；发送失败不阻塞注册响应）
    await sms_client.send_code(payload.phone, settings.SMS_REGISTER_TEMPLATE_CODE)

    return created_user
