"""UserManager - 用户生命周期管理与业务回调。"""
import logging
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi_users.exceptions import InvalidPasswordException

from app.audit import log_audit
from app.auth.sync_db import SyncSQLAlchemyUserDatabase
from app.core.config import settings
from app.db.models import User
from app.db.session import get_session
from app.services.sms_client import sms_client

logger = logging.getLogger(__name__)


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    """InnovOS UserManager - 集成审计日志与邮件回调。"""

    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.register", "user", str(user.id),
            {}, request.client.host if request else "",
        )
        # 注册后自动下发短信验证码（失败不阻塞注册响应）
        try:
            await sms_client.send_code(user.phone, settings.SMS_REGISTER_TEMPLATE_CODE)
        except Exception as e:  # noqa: BLE001
            logger.warning("短信下发失败: %s", e)

    async def on_after_login(
        self, user: User, request: Optional[Request] = None,
        response=None,
    ):
        log_audit(
            user.id, user.email, "user.login", "user", str(user.id),
            {}, request.client.host if request else "",
        )

    async def on_after_forgot_password(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        """InnovOS 不依赖此回调 — 重置密码走自研 OTP 流程(/api/auth/password-reset/*)。
        fastapi-users 的内置 reset router 仍保留挂载(向后兼容),但 InnovOS 前端不调用。
        """
        pass

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.verify", "user", str(user.id),
            {}, "",
        )

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(reason="密码至少 8 位")


async def get_user_db(session=Depends(get_session)):
    yield SyncSQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)