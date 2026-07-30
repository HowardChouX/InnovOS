# app/services/email_verification_service.py
import asyncio
import hashlib
import logging
import secrets
from enum import Enum
from typing import Any, Optional

import jwt
from fastapi import Request
from fastapi_users.jwt import generate_jwt, decode_jwt

from app.core.config import settings
from app.database import db_session
from app.exceptions.email_verification import (
    AlreadyVerified,
    CodeExhausted,
    CodeExpired,
    CodeInvalid,
    EmailNotFound,
    OtpRateLimited,
)
from app.exceptions.password_reset import InvalidResetSession
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


def _hash_code(code: str) -> str:
    return hashlib.sha256((code + (settings.OTP_PEPPER or "")).encode("utf-8")).hexdigest()


def _gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# ── OTP 用途枚举 ──────────────────────────────────────────────
class OtpPurpose(str, Enum):
    """邮件 OTP 的用途分类。

    用于在 email_verifications 表内隔离不同业务流程的 OTP 记录:
    - EMAIL_VERIFICATION: 注册 / 邮箱验证
    - PASSWORD_RESET: 密码重置
    """

    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


# ── reset session token helpers ────────────────────────────────────────


def _reset_session_jwt_secret() -> str:
    """优先用独立 secret,缺省回退到 SECRET_KEY(开发期不抛错)。"""
    return settings.RESET_SESSION_JWT_SECRET or settings.SECRET_KEY


def _issue_reset_session_token(user_id: int) -> str:
    """签发短时 JWT 作为密码重置阶段 2 的凭证。

    客户端拿到 token 后才能调 set_password_with_session 改密。
    """
    return generate_jwt(
        {
            "sub": str(user_id),
            "aud": settings.RESET_SESSION_JWT_AUDIENCE,
        },
        _reset_session_jwt_secret(),
        settings.RESET_SESSION_TOKEN_TTL_SECONDS,
    )


def _decode_reset_session_token(token: str) -> int:
    """解码 reset_session_token,返回 user_id。"""
    data = decode_jwt(
        token,
        _reset_session_jwt_secret(),
        [settings.RESET_SESSION_JWT_AUDIENCE],
    )
    return int(data["sub"])


class EmailVerificationService:
    @staticmethod
    def _now_sql(db) -> Any:
        return db.execute("SELECT NOW() AS now").fetchone()["now"]

    def issue_for_user(
        self,
        user,
        request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
        """下发指定用途的 OTP。purpose 必须显式指定,默认 EMAIL_VERIFICATION。"""
        with db_session() as db:
            # 同 (user, purpose) 之前的未消费 OTP 一并作废
            db.execute(
                "UPDATE email_verifications SET consumed_at = NOW() "
                "WHERE user_id=%s AND consumed_at IS NULL AND expires_at > NOW() "
                "AND purpose=%s",
                (user.id, purpose.value),
            )
            code = _gen_code()
            ttl = settings.OTP_TTL_SECONDS
            db.execute(
                "INSERT INTO email_verifications "
                "(user_id, email, code_hash, attempts, max_attempts, expires_at, last_sent_at, purpose) "
                "VALUES (%s, %s, %s, 0, %s, NOW() + (%s || ' seconds')::interval, NOW(), %s)",
                (
                    user.id, user.email, _hash_code(code),
                    settings.OTP_MAX_ATTEMPTS, str(ttl), purpose.value,
                ),
            )
        if purpose == OtpPurpose.PASSWORD_RESET:
            email_service.send_password_reset_otp_sync(user, code, request)
        else:
            email_service.send_verification_otp_sync(user, code, request)
        logger.info(
            "OTP issued user=%s purpose=%s expires_in=%s",
            user.id, purpose.value, ttl,
        )
        return {"expires_in": ttl, "next_resend_in": settings.OTP_RESEND_COOLDOWN}

    def resend(
        self,
        email: str,
        request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
        """重新下发指定用途的 OTP,受 resend cooldown 限流。"""
        with db_session() as db:
            user = db.execute(
                "SELECT id, email, is_verified FROM users WHERE email=%s", (email,)
            ).fetchone()
            if not user:
                raise EmailNotFound()
            # 只在 email_verification 流程里关心 is_verified
            if purpose == OtpPurpose.EMAIL_VERIFICATION and user["is_verified"]:
                raise AlreadyVerified()
            last = db.execute(
                "SELECT last_sent_at FROM email_verifications "
                "WHERE email=%s AND consumed_at IS NULL AND expires_at > NOW() "
                "AND purpose=%s "
                "ORDER BY id DESC LIMIT 1",
                (email, purpose.value),
            ).fetchone()
            if last:
                now = self._now_sql(db)
                diff = (now - last["last_sent_at"]).total_seconds()
                if diff < settings.OTP_RESEND_COOLDOWN:
                    raise OtpRateLimited(int(settings.OTP_RESEND_COOLDOWN - diff))
            # 构造轻量 user 供邮件服务使用
            class _U:
                pass

            u = _U()
            u.id = user["id"]
            u.email = user["email"]
            return self.issue_for_user(u, request, purpose=purpose)

    def verify(
        self,
        email: str,
        code: str,
        request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
        """校验指定用途的 OTP。

        EMAIL_VERIFICATION 成功 → 翻 is_verified,返回 {verified, already?}.
        PASSWORD_RESET 成功 → 签发 reset_session_token,返回 {verified, reset_token}.
        """
        _action: Optional[Exception] = None
        _user_id: Optional[int] = None
        _reset_token: Optional[str] = None
        with db_session() as db:
            user = db.execute(
                "SELECT id, email, is_verified FROM users WHERE email=%s", (email,)
            ).fetchone()
            if not user:
                raise EmailNotFound()
            if purpose == OtpPurpose.EMAIL_VERIFICATION and user["is_verified"]:
                return {"verified": True, "already": True}
            _user_id = user["id"]
            row = db.execute(
                "SELECT id, code_hash, attempts, max_attempts, expires_at FROM email_verifications "
                "WHERE email=%s AND consumed_at IS NULL AND purpose=%s "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (email, purpose.value),
            ).fetchone()
            if not row:
                raise CodeExpired()
            now = self._now_sql(db)
            if row["expires_at"] < now:
                db.execute(
                    "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s",
                    (row["id"],),
                )
                _action = CodeExpired()
            elif _hash_code(code) != row["code_hash"]:
                new_attempts = row["attempts"] + 1
                if new_attempts >= row["max_attempts"]:
                    db.execute(
                        "UPDATE email_verifications SET attempts=%s, consumed_at=NOW() WHERE id=%s",
                        (new_attempts, row["id"]),
                    )
                    _action = CodeExhausted()
                else:
                    db.execute(
                        "UPDATE email_verifications SET attempts=%s WHERE id=%s",
                        (new_attempts, row["id"]),
                    )
                    _action = CodeInvalid(row["max_attempts"] - new_attempts)
            else:
                # 主 OTP 消费
                db.execute(
                    "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s",
                    (row["id"],),
                )
                # 同 (email, purpose) 其他活跃 OTP 一并作废,防重放
                db.execute(
                    "UPDATE email_verifications SET consumed_at=NOW() "
                    "WHERE email=%s AND purpose=%s AND consumed_at IS NULL AND id<>%s",
                    (email, purpose.value, row["id"]),
                )
                if purpose == OtpPurpose.EMAIL_VERIFICATION:
                    db.execute(
                        "UPDATE users SET is_verified=TRUE, is_active=TRUE WHERE id=%s",
                        (user["id"],),
                    )
                else:
                    _reset_token = _issue_reset_session_token(user["id"])
        if _action is not None:
            raise _action
        if purpose == OtpPurpose.PASSWORD_RESET and _reset_token:
            logger.info("OTP verified (password_reset) user=%s", _user_id)
            return {"verified": True, "reset_token": _reset_token}
        logger.info("OTP verified user=%s", _user_id)
        return {"verified": True, "already": False}

    # ── Password reset session helpers (used by Task 6 routes) ──────────

    def consume_reset_session(self, token: str) -> int:
        """解码 reset_session_token 并返回 user_id。失败抛 InvalidResetSession。

        注意:这一步不写入数据库,token 本身的有效性由 JWT exp/aud 决定。
        """
        try:
            return _decode_reset_session_token(token)
        except (jwt.PyJWTError, KeyError, ValueError):
            raise InvalidResetSession()

    def set_password_with_session(
        self, token: str, new_password: str,
    ) -> dict[str, Any]:
        """用 reset_session_token 改密,走 UserManager 触发 bcrypt 哈希 + 审计 + 失效旧 JWT。

        流程:
        1. 解码 token → user_id
        2. 通过 SQLAlchemy Session + UserManager 调用 _update(password=...)
           (fastapi_users 内部会调用 password_helper.hash 走 bcrypt)
        """
        user_id = self.consume_reset_session(token)
        from app.db.session import _get_session_factory
        from app.db.models import User
        from app.auth.sync_db import SyncSQLAlchemyUserDatabase
        from app.auth.users import UserManager

        factory = _get_session_factory()
        session = factory()
        try:
            user_db = SyncSQLAlchemyUserDatabase(session, User)
            manager = UserManager(user_db)
            loop = asyncio.new_event_loop()
            try:
                user = loop.run_until_complete(manager.get(user_id))
                if not user:
                    raise InvalidResetSession()
                # password 字段是 fastapi_users 内部约定,会触发 hashed_password 重算
                loop.run_until_complete(
                    manager._update(user, {"password": new_password})
                )
            finally:
                loop.close()
        finally:
            session.close()
        return {"reset": True}

    def purge_expired(self, retention_days: int = 30) -> int:
        with db_session() as db:
            cur = db.execute(
                "DELETE FROM email_verifications "
                "WHERE (consumed_at IS NOT NULL AND consumed_at < NOW() - (%s || ' days')::interval) "
                "   OR (expires_at < NOW() - (%s || ' days')::interval)",
                (str(retention_days), str(retention_days)),
            )
            deleted = cur.rowcount
        logger.info("Purged %d expired email_verifications", deleted)
        return deleted


email_verification_service = EmailVerificationService()
