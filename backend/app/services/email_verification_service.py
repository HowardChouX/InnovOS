# app/services/email_verification_service.py
import hashlib
import logging
import secrets
from typing import Any, Optional

from fastapi import Request

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
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


def _hash_code(code: str) -> str:
    return hashlib.sha256((code + (settings.OTP_PEPPER or "")).encode("utf-8")).hexdigest()


def _gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class EmailVerificationService:
    def _now_sql(self, db) -> Any:
        return db.execute("SELECT NOW() AS now").fetchone()["now"]

    def issue_for_user(self, user, request: Optional[Request] = None) -> dict[str, Any]:
        with db_session() as db:
            db.execute(
                "UPDATE email_verifications SET consumed_at = NOW() "
                "WHERE user_id=%s AND consumed_at IS NULL AND expires_at > NOW()",
                (user.id,),
            )
            code = _gen_code()
            ttl = settings.OTP_TTL_SECONDS
            db.execute(
                "INSERT INTO email_verifications "
                "(user_id, email, code_hash, attempts, max_attempts, expires_at, last_sent_at) "
                "VALUES (%s, %s, %s, 0, %s, NOW() + (%s || ' seconds')::interval, NOW())",
                (user.id, user.email, _hash_code(code), settings.OTP_MAX_ATTEMPTS, str(ttl)),
            )
        email_service.send_verification_otp_sync(user, code, request)
        return {"expires_in": ttl, "next_resend_in": settings.OTP_RESEND_COOLDOWN}

    def resend(self, email: str, request: Optional[Request] = None) -> dict[str, Any]:
        with db_session() as db:
            user = db.execute(
                "SELECT id, email, is_verified FROM users WHERE email=%s", (email,)
            ).fetchone()
            if not user:
                raise EmailNotFound()
            if user["is_verified"]:
                raise AlreadyVerified()
            last = db.execute(
                "SELECT last_sent_at FROM email_verifications "
                "WHERE email=%s AND consumed_at IS NULL AND expires_at > NOW() "
                "ORDER BY id DESC LIMIT 1",
                (email,),
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
        return self.issue_for_user(u, request)

    def verify(self, email: str, code: str, request: Optional[Request] = None) -> dict[str, Any]:
        with db_session() as db:
            user = db.execute(
                "SELECT id, email, is_verified FROM users WHERE email=%s", (email,)
            ).fetchone()
            if not user:
                raise EmailNotFound()
            if user["is_verified"]:
                return {"verified": True, "already": True}
            row = db.execute(
                "SELECT id, code_hash, attempts, max_attempts, expires_at FROM email_verifications "
                "WHERE email=%s AND consumed_at IS NULL "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (email,),
            ).fetchone()
            if not row:
                raise CodeExpired()
            now = self._now_sql(db)
            if row["expires_at"] < now:
                db.execute(
                    "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s", (row["id"],)
                )
                raise CodeExpired()
            if _hash_code(code) != row["code_hash"]:
                new_attempts = row["attempts"] + 1
                if new_attempts >= row["max_attempts"]:
                    db.execute(
                        "UPDATE email_verifications SET attempts=%s, consumed_at=NOW() WHERE id=%s",
                        (new_attempts, row["id"]),
                    )
                    raise CodeExhausted()
                db.execute(
                    "UPDATE email_verifications SET attempts=%s WHERE id=%s",
                    (new_attempts, row["id"]),
                )
                raise CodeInvalid(row["max_attempts"] - new_attempts)
            db.execute(
                "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s", (row["id"],)
            )
            db.execute(
                "UPDATE users SET is_verified=TRUE, is_active=TRUE WHERE id=%s", (user["id"],)
            )
        return {"verified": True, "already": False}

    def purge_expired(self, retention_days: int = 30) -> int:
        with db_session() as db:
            cur = db.execute(
                "DELETE FROM email_verifications "
                "WHERE (consumed_at IS NOT NULL AND consumed_at < NOW() - (%s || ' days')::interval) "
                "   OR (expires_at < NOW() - (%s || ' days')::interval)",
                (str(retention_days), str(retention_days)),
            )
            return cur.rowcount


email_verification_service = EmailVerificationService()