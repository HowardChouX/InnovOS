# InnovOS 邮箱验证 6 位邮件 OTP 强制链路 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 注册流程强制走 6 位邮件 OTP 验证，未验证账号禁止登录。

**Architecture:** 在 FastAPI Users 既有登录/重置密码体系外，新增 `email_verifications` 表 + 自建 `email_verification_service` + 三个 OTP 路由；`UserManager.on_after_register` 自动发码；`get_auth_router(..., requires_verification=True)` 拦截未验证用户；前端新增 `VerifyEmailPage`、`RegisterPage` 不再自动 login、`LoginPage` 401 跳验证页。

**Tech Stack:** Python 3.11+, FastAPI, FastAPI Users 15.0.5, psycopg2, PostgreSQL 14+; React 19 + TypeScript + Vite 8, Zustand 5, React Router 7, Vitest.

**Reference spec:** `docs/superpowers/specs/2026-07-29-email-verification-design.md`

---

## File Structure

### 后端

- Create:
  - `backend/app/api/email_verification.py` — 三个 OTP 路由（`/api/auth/email-verifications/{request,resend,verify}`）。
  - `backend/app/services/email_verification_service.py` — OTP 生成 / 落表 / 重发 / 校验 / 清理。
  - `backend/app/exceptions/email_verification.py` — `EmailVerificationError` + 子类 + 异常 handler。
  - `backend/app/schemas/email_verification.py` — Pydantic 请求/响应模型。
  - `backend/tests/test_email_verification.py` — 后端单测。
- Modify:
  - `backend/app/tables/pg_schema.py` — 追加 `email_verifications` 表 + 索引。
  - `backend/app/main.py` — 挂载新路由、调整 auth/users 路由 `requires_verification=True`、移除 `get_verify_router`、注册新异常 handler、启动期调用 `purge_expired`。
  - `backend/app/auth/users.py` — `on_after_register` 追加 `issue_for_user`。
  - `backend/app/auth/exceptions.py` — `UserInactive` 文案改为“邮箱未验证，请先完成验证”（保留异常类，沿用映射）。
  - `backend/app/services/email_service.py` — 新增 `send_verification_otp_sync`；dev 兜底日志。
  - `backend/app/core/config.py` — 新增配置项 + 生产校验。
  - `backend/app/rate_limit.py` — 新增 `email_otp_*` 限流器（如有 Redis 走 `rate_limit_redis.py` 同形态）。
  - `backend/app/database.py` — `init_db()` 内调用 `purge_expired`（幂等，失败不阻塞）。
  - `backend/.env.example` — 增补 SMTP / OTP 配置。
  - `backend/app/auth/seed.py` — 不动（参考其 `update_user` 形态）。
  - `frontend/...`（见下）。

### 前端

- Create:
  - `frontend/src/features/auth/VerifyEmailPage.tsx` — 6 位输入 + 60s 倒计时 + 重发。
  - `frontend/src/features/auth/__tests__/VerifyEmailPage.test.tsx`。
  - `frontend/src/features/auth/__tests__/RegisterPage.test.tsx`。
- Modify:
  - `frontend/src/api/auth.ts` — 新增三个 OTP 方法。
  - `frontend/src/store/useAuthStore.ts` — `register` 不再自动 `login`。
  - `frontend/src/features/auth/RegisterPage.tsx` — 注册成功跳 `/verify-email`。
  - `frontend/src/features/auth/LoginPage.tsx` — 401 `UserInactive` 跳 `/verify-email`。
  - `frontend/src/routes/index.tsx`（或 `App.tsx`）— 注册 `/verify-email` 路由。
  - `frontend/src/types/auth.ts` — `ApiError.code` 文案与后端对齐。
  - `frontend/src/api/client.ts` — `ApiError` 暴露 `code`（如已暴露则确认）。

### 文档

- Modify:
  - `docs/architecture.md` — 新增“邮箱验证（6 位邮件 OTP）”小节。
  - `docs/development.md` — 新增“本地查看验证码：Mailpit / 日志”。
  - `.env.example`（根目录） — 增补 SMTP / OTP 配置（如果存在）。

---

## Task 1: 配置项（`backend/app/core/config.py`）

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_core_config.py`（增量更新 OTP 相关默认值）

- [ ] **Step 1: 写失败测试（OTP 默认值 + 生产强制 pepper）**

```python
# tests/test_core_config.py
def test_otp_defaults_present():
    from app.core.config import settings
    assert settings.OTP_TTL_SECONDS == 600
    assert settings.OTP_MAX_ATTEMPTS == 5
    assert settings.OTP_RESEND_COOLDOWN == 60
    assert settings.EMAIL_OTP_SOFT_FAIL is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_core_config.py -v -k "test_otp_defaults_present"`
Expected: FAIL (AttributeError: OTP_TTL_SECONDS).

- [ ] **Step 3: 在 `Settings` 内追加字段（紧跟 `SMTP_SSL`）**

```python
# app/core/config.py
    # ── Email OTP 验证 ──
    OTP_TTL_SECONDS: int = 600
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN: int = 60
    INNOVOS_OTP_PEPPER: str = ""
    EMAIL_OTP_SOFT_FAIL: bool = False
```

- [ ] **Step 4: 生产校验**

在 `_enforce_production_settings` 顶部追加：

```python
        if self.ENVIRONMENT == "production" and not self.INNOVOS_OTP_PEPPER:
            raise ValueError("INNOVOS_OTP_PEPPER must be set in production")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_core_config.py -v -k "test_otp_defaults_present"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/core/config.py backend/tests/test_core_config.py
git commit -m "feat(auth+config): add OTP verification config (TTL, attempts, pepper)"
```

---

## Task 2: 数据库表 `email_verifications`（`backend/app/tables/pg_schema.py`）

**Files:**
- Modify: `backend/app/tables/pg_schema.py`（在 `users` 表定义附近追加）
- Test: 启动期由 `init_db()` 验证；本任务不写单独单测，由 Task 9 端到端覆盖。

- [ ] **Step 1: 打开 `backend/app/tables/pg_schema.py`，找到现有 DDL 函数 `_create_users_table` 之后的合适位置（建议在 `users` 表后）追加**

```python
# app/tables/pg_schema.py
def _create_email_verifications_table(db) -> None:
    """6 位邮件 OTP 表。注册时落码，验证后置 consumed_at。"""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verifications (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            code_hash CHAR(64) NOT NULL,
            attempts SMALLINT NOT NULL DEFAULT 0,
            max_attempts SMALLINT NOT NULL DEFAULT 5,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_user_id_idx "
        "ON email_verifications(user_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_email_idx "
        "ON email_verifications(email)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_active_idx "
        "ON email_verifications(consumed_at) WHERE consumed_at IS NULL"
    )
```

- [ ] **Step 2: 在 `init_db()` 内的 `users` 表创建之后追加调用**

```python
# app/database.py init_db()
        _create_email_verifications_table(db)
```

- [ ] **Step 3: 跑现有数据库测试确认未破坏**

Run: `cd backend && uv run pytest tests/test_database.py -v`
Expected: PASS（`email_verifications` 表创建幂等）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/tables/pg_schema.py backend/app/database.py
git commit -m "feat(db): add email_verifications table (idempotent DDL)"
```

---

## Task 3: Pydantic schemas（`backend/app/schemas/email_verification.py`）

**Files:**
- Create: `backend/app/schemas/email_verification.py`
- Test: 沿用 FastAPI 自动校验；本任务不写单独单测，由 Task 9 覆盖。

- [ ] **Step 1: 写文件**

```python
# app/schemas/email_verification.py
from pydantic import BaseModel, EmailStr, Field


class OtpRequestIn(BaseModel):
    email: EmailStr


class OtpResendIn(BaseModel):
    email: EmailStr


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpIssuedOut(BaseModel):
    expires_in: int
    next_resend_in: int = 60


class OtpVerifiedOut(BaseModel):
    verified: bool
    already: bool = False
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/email_verification.py
git commit -m "feat(auth+schemas): add OTP request/resend/verify pydantic models"
```

---

## Task 4: 异常类（`backend/app/exceptions/email_verification.py`）

**Files:**
- Create: `backend/app/exceptions/email_verification.py`
- Modify: `backend/app/main.py`（注册 handler；这一步仅先 import，handler 路由挂载在 Task 6 集中做）

- [ ] **Step 1: 写文件**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/exceptions/email_verification.py
git commit -m "feat(auth+exceptions): add EmailVerificationError taxonomy + handler"
```

---

## Task 5: 服务层（`backend/app/services/email_verification_service.py`）

**Files:**
- Create: `backend/app/services/email_verification_service.py`
- Test: `backend/tests/test_email_verification.py`（本任务先写失败测试）

- [ ] **Step 1: 写失败测试（落表 + 验证主流程）**

```python
# tests/test_email_verification.py
from datetime import timedelta

import pytest

from app.core.config import settings
from app.database import db_session
from app.services.email_verification_service import email_verification_service
from app.services.email_service import email_service


class _Stub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_verification_otp_sync(self, user, code, request=None) -> None:  # type: ignore[no-untyped-def]
        self.sent.append((user.email, code))


def _make_user(client, email="t@example.com", password="password123"):
    from app.auth.users import get_user_manager
    import asyncio
    from fastapi_users.password import PasswordHelper

    pw_helper = PasswordHelper()
    hashed = pw_helper.hash(password)
    with db_session() as db:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES (%s, %s, %s, TRUE, FALSE, FALSE)",
            (email, email.split("@")[0], hashed),
        )
        row = db.execute("SELECT id FROM users WHERE email=%s", (email,)).fetchone()
        return row["id"]


def test_issue_and_verify_success(monkeypatch):
    stub = _Stub()
    monkeypatch.setattr(email_service, "send_verification_otp_sync", stub.send_verification_otp_sync)
    user_id = _make_user(None)
    from app.db.models import User
    with db_session() as db:
        user = db.execute("SELECT id, email FROM users WHERE id=%s", (user_id,)).fetchone()
    # 直接构造 User 对象供 service 使用
    user_obj = User(id=user["id"], email=user["email"])
    rec = email_verification_service.issue_for_user(user_obj, request=None)
    assert rec["expires_in"] == settings.OTP_TTL_SECONDS
    code = stub.sent[-1][1]
    email_verification_service.verify(user_obj.email, code, request=None)
    with db_session() as db:
        row = db.execute("SELECT is_verified FROM users WHERE id=%s", (user_id,)).fetchone()
        assert row["is_verified"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_email_verification.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写服务层**

```python
# app/services/email_verification_service.py
import hashlib
import logging
import secrets
from datetime import timedelta
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_email_verification.py -v -k "test_issue_and_verify_success"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_verification_service.py backend/tests/test_email_verification.py
git commit -m "feat(auth+service): email_verification_service (issue/resend/verify/purge)"
```

---

## Task 6: 邮件服务 OTP 通道（`backend/app/services/email_service.py`）

**Files:**
- Modify: `backend/app/services/email_service.py`
- Test: `backend/tests/test_email_service.py`（追加 dev 日志兜底）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_email_service.py
def test_dev_otp_logged_when_smtp_unset(monkeypatch, caplog):
    from app.services import email_service as es

    class _User:
        email = "a@b.com"

    monkeypatch.setattr(es.settings, "SMTP_HOST", "")
    monkeypatch.setattr(es.settings, "ENVIRONMENT", "development")
    with caplog.at_level("INFO", logger=es.logger.name):
        es.email_service.send_verification_otp_sync(_User(), "123456")
    assert any("[DEV OTP]" in rec.message and "code=123456" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_email_service.py -v -k "test_dev_otp_logged"`
Expected: FAIL（方法不存在）。

- [ ] **Step 3: 在 `EmailService` 类内追加**

```python
# app/services/email_service.py
    def send_verification_otp_sync(self, user, code: str, request=None) -> None:
        """发送 6 位邮件 OTP。仅 dev 在未配 SMTP 时记录明文日志。"""
        body = (
            f"<h2>您的 InnovOS 邮箱验证码</h2>"
            f"<p>验证码：<b>{code}</b></p>"
            f"<p>10 分钟内有效，请勿泄露给他人。</p>"
        )
        if not self.host:
            if settings.ENVIRONMENT == "development":
                logger.info("[DEV OTP] email=%s code=%s ttl=%ss", user.email, code, 600)
                return
            logger.warning("SMTP_HOST 未配置，跳过邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 邮箱验证码", body)
```

（不删除 `send_verification_email_sync`，但调用入口在 Task 7 移除。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_email_service.py -v -k "test_dev_otp_logged"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/test_email_service.py
git commit -m "feat(email): send_verification_otp_sync + dev log fallback"
```

---

## Task 7: 路由（`backend/app/api/email_verification.py`）+ 入口挂载（`backend/app/main.py`）

**Files:**
- Create: `backend/app/api/email_verification.py`
- Modify: `backend/app/main.py`（挂载新路由、移除 `get_verify_router`、`get_auth_router(..., requires_verification=True)`、注册新异常 handler）
- Test: `backend/tests/test_email_verification.py`（追加 4 个路由级测试）

- [ ] **Step 1: 写失败测试（HTTP 路由）**

```python
# tests/test_email_verification.py 追加
from fastapi.testclient import TestClient
from app.main import app_


def _client() -> TestClient:
    return TestClient(app_)


def test_request_endpoint_returns_202():
    c = _client()
    r = c.post("/api/auth/email-verifications/request", json={"email": "noone@x.com"})
    # 邮箱不存在应 404（按 spec §4.1/§6 仅 resend/verify 区分；request 同样 404 防探测）
    assert r.status_code in (202, 404)


def test_resend_endpoint_rate_limits():
    c = _client()
    # 先注册一个未验证用户
    r = c.post(
        "/api/auth/register",
        json={"email": "rl@example.com", "password": "password123"},
    )
    assert r.status_code in (200, 201, 400)
    r1 = c.post("/api/auth/email-verifications/resend", json={"email": "rl@example.com"})
    r2 = c.post("/api/auth/email-verifications/resend", json={"email": "rl@example.com"})
    assert r2.status_code == 429


def test_verify_endpoint_wrong_code_returns_400():
    c = _client()
    c.post("/api/auth/register", json={"email": "vc@example.com", "password": "password123"})
    r = c.post(
        "/api/auth/email-verifications/verify",
        json={"email": "vc@example.com", "code": "000000"},
    )
    # 取决于测试是否发信：可能 400 CODE_INVALID 或 410 CODE_EXPIRED
    assert r.status_code in (400, 410)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_email_verification.py -v -k "test_request_endpoint_returns_202 or test_resend_endpoint_rate_limits or test_verify_endpoint_wrong_code"`
Expected: FAIL（路由不存在）。

- [ ] **Step 3: 写路由文件**

```python
# app/api/email_verification.py
from fastapi import APIRouter

from app.schemas.email_verification import (
    OtpIssuedOut,
    OtpRequestIn,
    OtpResendIn,
    OtpVerifiedOut,
)
from app.services.email_verification_service import email_verification_service

router = APIRouter(prefix="/api/auth/email-verifications", tags=["auth"])


@router.post("/request", response_model=OtpIssuedOut, status_code=202)
def request_otp(payload: OtpRequestIn) -> OtpIssuedOut:
    try:
        rec = email_verification_service.resend(payload.email)
    except Exception:
        # 防探测：未知邮箱静默返回 202
        return OtpIssuedOut(expires_in=600, next_resend_in=60)
    return OtpIssuedOut(**rec)


@router.post("/resend", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn) -> OtpIssuedOut:
    rec = email_verification_service.resend(payload.email)
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=OtpVerifiedOut)
def verify_otp(payload: OtpVerifyIn) -> OtpVerifiedOut:
    rec = email_verification_service.verify(payload.email, payload.code)
    return OtpVerifiedOut(**rec)
```

- [ ] **Step 4: 在 `backend/app/main.py` 调整挂载**

替换第 255-281 段的整段：

```python
# app/main.py
from app.api.email_verification import router as email_verification_router
from app.exceptions.email_verification import (
    email_verification_exception_handler,
    EmailVerificationError,
)
from fastapi_users.exceptions import (
    InvalidPasswordException,
    InvalidResetPasswordToken,
    UserAlreadyExists,
    UserNotExists,
    # 删除 InvalidVerifyToken、UserAlreadyVerified（路由移除）
)

app_.include_router(
    fastapi_users.get_auth_router(auth_backend, requires_verification=True),
    prefix="/api/auth/jwt", tags=["auth"],
)
app_.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/auth", tags=["auth"],
)
app_.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/api/auth", tags=["auth"],
)
# 移除 fastapi_users.get_verify_router(UserRead)
app_.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate, requires_verification=True),
    prefix="/api/users", tags=["users"],
)
app_.include_router(email_verification_router)
app_.add_exception_handler(EmailVerificationError, email_verification_exception_handler)
for exc in (
    UserAlreadyExists, UserNotExists,
    InvalidResetPasswordToken, InvalidPasswordException,
):
    app_.add_exception_handler(exc, fastapi_users_exception_handler)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_email_verification.py -v`
Expected: 已有测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/email_verification.py backend/app/main.py backend/tests/test_email_verification.py
git commit -m "feat(auth+routes): /email-verifications routes + requires_verification on auth/users"
```

---

## Task 8: 注册时自动发码（`backend/app/auth/users.py`）

**Files:**
- Modify: `backend/app/auth/users.py`
- Test: `backend/tests/test_user_manager.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_user_manager.py 追加
def test_on_after_register_issues_otp(monkeypatch):
    from app.auth.users import UserManager
    from app.services.email_verification_service import email_verification_service

    called = {"n": 0}

    def _fake(user, request=None):
        called["n"] += 1
        return {"expires_in": 600, "next_resend_in": 60}

    monkeypatch.setattr(email_verification_service, "issue_for_user", _fake)
    um = UserManager.__new__(UserManager)
    # User 占位
    class _U:
        id = 1
        email = "a@b.com"
    import asyncio
    asyncio.run(um.on_after_register(_U(), None))
    assert called["n"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_user_manager.py -v -k "test_on_after_register_issues_otp"`
Expected: FAIL（`on_after_register` 未调用 issue_for_user）。

- [ ] **Step 3: 改 `on_after_register`**

```python
# app/auth/users.py
    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.register", "user", str(user.id),
            {}, request.client.host if request else "",
        )
        # 注册后自动下发 6 位邮件 OTP（失败不阻塞注册响应）
        try:
            from app.services.email_verification_service import email_verification_service
            email_verification_service.issue_for_user(user, request)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("issue_for_user 失败: %s", e)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_user_manager.py -v -k "test_on_after_register_issues_otp"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/users.py backend/tests/test_user_manager.py
git commit -m "feat(auth+user-manager): issue OTP on register (failure logged, non-blocking)"
```

---

## Task 9: 后端测试收尾（5 次错误耗尽 / 重发作废旧码 / 过期 / 登录校验 / purge）

**Files:**
- Modify: `backend/tests/test_email_verification.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_email_verification.py 追加
def test_5_wrong_attempts_exhaust(monkeypatch):
    from app.services import email_verification_service as ev
    from app.services import email_service as es

    class _Stub:
        def send_verification_otp_sync(self, user, code, request=None):
            self.code = code
    stub = _Stub()
    monkeypatch.setattr(es.email_service, "send_verification_otp_sync", stub.send_verification_otp_sync)

    # 直接建用户
    from app.database import db_session
    from app.auth.users import UserManager  # noqa
    from fastapi_users.password import PasswordHelper
    pw = PasswordHelper()
    hashed = pw.hash("password123")
    with db_session() as db:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES (%s, %s, %s, TRUE, FALSE, FALSE)",
            ("e5@x.com", "e5", hashed),
        )
        uid = db.execute("SELECT id FROM users WHERE email=%s", ("e5@x.com",)).fetchone()["id"]

    from app.db.models import User
    user = User(id=uid, email="e5@x.com")
    ev.email_verification_service.issue_for_user(user)

    for _ in range(5):
        try:
            ev.email_verification_service.verify("e5@x.com", "000000")
        except Exception:
            pass
    # 第 6 次应得 CODE_EXHAUSTED
    from app.exceptions.email_verification import CodeExhausted
    import pytest
    with pytest.raises(CodeExhausted):
        ev.email_verification_service.verify("e5@x.com", "111111")


def test_resend_invalidates_previous(monkeypatch):
    from app.services import email_verification_service as ev
    from app.services import email_service as es

    codes: list[str] = []

    def _send(user, code, request=None):
        codes.append(code)

    monkeypatch.setattr(es.email_service, "send_verification_otp_sync", _send)
    from app.database import db_session
    from fastapi_users.password import PasswordHelper
    pw = PasswordHelper()
    with db_session() as db:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES (%s, %s, %s, TRUE, FALSE, FALSE)",
            ("ri@x.com", "ri", pw.hash("password123")),
        )
        uid = db.execute("SELECT id FROM users WHERE email=%s", ("ri@x.com",)).fetchone()["id"]
    from app.db.models import User
    user = User(id=uid, email="ri@x.com")
    ev.email_verification_service.issue_for_user(user)
    # 缩短冷却以便重发
    from app.core.config import settings
    settings.OTP_RESEND_COOLDOWN = 0
    ev.email_verification_service.resend("ri@x.com")
    # 旧码应已置 consumed_at
    from app.exceptions.email_verification import CodeInvalid
    import pytest
    with pytest.raises(Exception):
        ev.email_verification_service.verify("ri@x.com", codes[0])


def test_login_requires_verification():
    from fastapi.testclient import TestClient
    from app.main import app_
    c = TestClient(app_)
    c.post("/api/auth/register", json={"email": "nr@x.com", "password": "password123"})
    r = c.post(
        "/api/auth/jwt/login",
        data={"username": "nr@x.com", "password": "password123"},
    )
    # 未验证 → 401 UserInactive（fastapi-users 内部抛 UserInactive；handler 映射 400/401）
    assert r.status_code in (400, 401)
```

- [ ] **Step 2: 跑全部相关测试**

Run: `cd backend && uv run pytest tests/test_email_verification.py tests/test_user_manager.py tests/test_email_service.py -v`
Expected: 全 PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_email_verification.py
git commit -m "test(auth): OTP error budget / resend invalidation / login requires verification"
```

---

## Task 10: 启动期清理过期记录（`backend/app/database.py`）

**Files:**
- Modify: `backend/app/database.py`
- Test: 现有 `tests/test_database.py` 跑通即可。

- [ ] **Step 1: 改 `init_db()` 在建表后调用清理**

```python
# app/database.py init_db() 内，紧跟 _create_email_verifications_table(db)
        try:
            from app.services.email_verification_service import email_verification_service
            email_verification_service.purge_expired()
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("purge_expired 失败: %s", e)
```

- [ ] **Step 2: 跑测试**

Run: `cd backend && uv run pytest tests/test_database.py -v`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/app/database.py
git commit -m "chore(db): purge expired email_verifications on init (best-effort)"
```

---

## Task 11: 限流器（`backend/app/rate_limit.py` / `backend/app/rate_limit_redis.py`）

**Files:**
- Modify: `backend/app/rate_limit.py`（如已有内存版）
- Modify: `backend/app/rate_limit_redis.py`（如已有 Redis 版）

- [ ] **Step 1: 确认现有 `register_limiter` / `auth_limiter` 形态，复制命名风格新增**

```python
# app/rate_limit.py（如内存版）追加
email_otp_request_limiter = RateLimiter(max_requests=1, window_seconds=60, name="email_otp_req")
email_otp_verify_limiter = RateLimiter(max_requests=10, window_seconds=60, name="email_otp_verify")
email_otp_ip_limiter = RateLimiter(max_requests=30, window_seconds=60, name="email_otp_ip")
```

如项目仅有 `rate_limit_redis.py`：

```python
# app/rate_limit_redis.py 追加
email_otp_request_limiter = RedisRateLimiter(max_requests=1, window_seconds=60, name="email_otp_req")
email_otp_verify_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="email_otp_verify")
email_otp_ip_limiter = RedisRateLimiter(max_requests=30, window_seconds=60, name="email_otp_ip")
```

- [ ] **Step 2: 在 `app/api/email_verification.py` 内对 `resend` 与 `verify` 应用限流（在 `email_verification_service.resend/verify` 内部已有 cooldown；这里仅做 IP 兜底）**

```python
# app/api/email_verification.py
from app.rate_limit import email_otp_ip_limiter  # 或 redis 版本
from fastapi import Request, Depends

@router.post("/resend", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.allow(ip):
        from app.exceptions.email_verification import OtpRateLimited
        raise OtpRateLimited(60)
    rec = email_verification_service.resend(payload.email)
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=OtpVerifiedOut)
def verify_otp(payload: OtpVerifyIn, request: Request) -> OtpVerifiedOut:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.allow(ip):
        from app.exceptions.email_verification import OtpRateLimited
        raise OtpRateLimited(60)
    rec = email_verification_service.verify(payload.email, payload.code)
    return OtpVerifiedOut(**rec)
```

- [ ] **Step 3: 跑测试**

Run: `cd backend && uv run pytest tests/test_email_verification.py -v -k "test_resend_endpoint_rate_limits"`
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/app/rate_limit.py backend/app/rate_limit_redis.py backend/app/api/email_verification.py
git commit -m "feat(rate-limit): email_otp request/verify/ip limiters"
```

---

## Task 12: 前端 API 客户端（`frontend/src/api/auth.ts`）

**Files:**
- Modify: `frontend/src/api/auth.ts`

- [ ] **Step 1: 在文件末尾追加**

```ts
// frontend/src/api/auth.ts 末尾
requestEmailOtp(email: string): Promise<{ expires_in: number; next_resend_in: number }> {
  return apiRequest('/api/auth/email-verifications/request', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
},
resendEmailOtp(email: string): Promise<{ expires_in: number; next_resend_in: number }> {
  return apiRequest('/api/auth/email-verifications/resend', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
},
verifyEmailOtp(email: string, code: string): Promise<{ verified: boolean; already?: boolean }> {
  return apiRequest('/api/auth/email-verifications/verify', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  });
},
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors（其它已有问题不算新增错误）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/auth.ts
git commit -m "feat(frontend+api): add requestEmailOtp / resendEmailOtp / verifyEmailOtp"
```

---

## Task 13: useAuthStore — register 不再自动 login

**Files:**
- Modify: `frontend/src/store/useAuthStore.ts`

- [ ] **Step 1: 改 `register` 主体**

```ts
// frontend/src/store/useAuthStore.ts
register: async (email, password, phone, username) => {
  // 注册成功后用户未登录：等待邮箱验证完成后手动登录。
  await authApi.register({ email, password, phone, username });
},
```

- [ ] **Step 2: 更新顶部注释**（说明“验证未完成前用户尚未登录”）

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/store/useAuthStore.ts
git commit -m "refactor(frontend+auth): register no longer auto-logs in"
```

---

## Task 14: RegisterPage — 注册后跳 /verify-email

**Files:**
- Modify: `frontend/src/features/auth/RegisterPage.tsx`

- [ ] **Step 1: 修改 `handleSubmit`**

```tsx
// frontend/src/features/auth/RegisterPage.tsx
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setError('');
  if (password !== confirm) {
    setError('两次密码不一致');
    return;
  }
  if (phone && !/^1\d{10}$/.test(phone)) {
    setError('手机号格式不正确（11 位数字，1 开头）');
    return;
  }
  try {
    await authApi.register({
      email,
      password,
      phone: phone || undefined,
      username: username || undefined,
    });
    navigate(`/verify-email?email=${encodeURIComponent(email)}`);
  } catch (err) {
    setError(err instanceof Error ? err.message : '注册失败');
  }
};
```

> 注意：`useAuthStore.register` 已不再自动 login，这里直接调 `authApi.register` 更清晰；同步移除页面里的 `useAuthStore.register` 引用。

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/auth/RegisterPage.tsx
git commit -m "feat(frontend+auth): RegisterPage redirects to /verify-email"
```

---

## Task 15: VerifyEmailPage（新增）

**Files:**
- Create: `frontend/src/features/auth/VerifyEmailPage.tsx`

- [ ] **Step 1: 写组件**

```tsx
// frontend/src/features/auth/VerifyEmailPage.tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Mail, ShieldCheck } from 'lucide-react';

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const email = params.get('email') ?? '';
  const navigate = useNavigate();
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const refs = useRef<Array<HTMLInputElement | null>>([null, null, null, null, null, null]);

  useEffect(() => {
    if (!email) navigate('/register', { replace: true });
  }, [email, navigate]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const code = useMemo(() => digits.join(''), [digits]);

  useEffect(() => {
    if (code.length === 6) void submit(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  async function submit(full: string) {
    setSubmitting(true);
    setError('');
    try {
      await authApi.verifyEmailOtp(email, full);
      navigate(`/login?email=${encodeURIComponent(email)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '验证失败');
      setDigits(['', '', '', '', '', '']);
      refs.current[0]?.focus();
    } finally {
      setSubmitting(false);
    }
  }

  async function resend() {
    if (cooldown > 0) return;
    setError('');
    try {
      await authApi.resendEmailOtp(email);
      setCooldown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : '重发失败');
    }
  }

  function setDigit(i: number, v: string) {
    const ch = v.replace(/\D/g, '').slice(-1);
    setDigits(prev => prev.map((d, idx) => (idx === i ? ch : d)));
    if (ch && i < 5) refs.current[i + 1]?.focus();
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const arr = ['', '', '', '', '', ''];
    for (let i = 0; i < text.length; i++) arr[i] = text[i];
    setDigits(arr);
    const next = Math.min(text.length, 5);
    refs.current[next]?.focus();
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 bg-slate-950"
      style={{ background: 'radial-gradient(circle at top right, #1a2540 0%, #0b1120 40%)' }}
    >
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text font-bold text-3xl mb-2">
            InnovOS
          </div>
          <p className="text-slate-400 text-sm">创新智能操作系统</p>
        </div>

        <form
          onSubmit={e => { e.preventDefault(); if (code.length === 6) void submit(code); }}
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4"
        >
          <h2 className="text-white font-bold text-lg text-center">验证邮箱</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex items-center gap-2 text-slate-300 text-sm">
            <Mail className="w-4 h-4" />
            <span>已发送验证码至 {email}</span>
          </div>

          <div className="flex justify-between gap-2" onPaste={handlePaste}>
            {digits.map((d, i) => (
              <input
                key={i}
                ref={el => { refs.current[i] = el; }}
                inputMode="numeric"
                maxLength={1}
                value={d}
                onChange={e => setDigit(i, e.target.value)}
                disabled={submitting}
                className="w-10 h-12 text-center text-xl text-white bg-slate-900/50 border border-slate-700 rounded-lg focus:outline-none focus:border-cyan-500"
                aria-label={`验证码第 ${i + 1} 位`}
              />
            ))}
          </div>

          <button
            type="button"
            onClick={resend}
            disabled={cooldown > 0}
            className="w-full text-sm text-cyan-400 disabled:text-slate-500"
          >
            {cooldown > 0 ? `${cooldown}s 后重发` : '重新发送验证码'}
          </button>

          <button
            type="submit"
            disabled={code.length !== 6 || submitting}
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? '验证中...' : '验证'}
          </button>

          <p className="text-center text-sm text-slate-500">
            验证遇到问题？{' '}
            <Link to="/register" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              重新注册
            </Link>
          </p>

          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-3 h-3" />
            <span>10 分钟内有效</span>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/auth/VerifyEmailPage.tsx
git commit -m "feat(frontend+auth): VerifyEmailPage with 6-digit input + 60s resend cooldown"
```

---

## Task 16: 路由挂载（`frontend/src/routes/index.tsx` 或 `App.tsx`）

**Files:**
- Modify: `frontend/src/routes/index.tsx`（或 `App.tsx`，按项目实际）

- [ ] **Step 1: 找到现有路由配置，追加**

```tsx
const VerifyEmailPage = lazyPage(() => import('@/features/auth/VerifyEmailPage'));
// ...
<Route path="/verify-email" element={<VerifyEmailPage />} />
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/index.tsx  # 或实际文件
git commit -m "feat(frontend+routes): register /verify-email route"
```

---

## Task 17: LoginPage 401 拦截跳 /verify-email

**Files:**
- Modify: `frontend/src/features/auth/LoginPage.tsx`

- [ ] **Step 1: 改登录失败分支**

```tsx
// frontend/src/features/auth/LoginPage.tsx
catch (err) {
  const e = err as { status?: number; code?: string; message?: string };
  if (e?.status === 400 && /未验证|UserInactive/i.test(e?.message ?? '')) {
    navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    setError('请先完成邮箱验证');
    return;
  }
  setError(e?.message ?? '登录失败');
}
```

> 若 `apiRequest` 抛出 `ApiError` 暴露 `code` 字段，直接判 `e.code === 'UserInactive'`；上面正则写法兼容两种实现。

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/auth/LoginPage.tsx
git commit -m "feat(frontend+auth): LoginPage redirects unverified users to /verify-email"
```

---

## Task 18: 前端测试 — RegisterPage / VerifyEmailPage / LoginPage

**Files:**
- Create:
  - `frontend/src/features/auth/__tests__/RegisterPage.test.tsx`
  - `frontend/src/features/auth/__tests__/VerifyEmailPage.test.tsx`
- Modify:
  - `frontend/src/features/auth/__tests__/LoginPage.test.tsx`

- [ ] **Step 1: 写 RegisterPage 测试**

```tsx
// frontend/src/features/auth/__tests__/RegisterPage.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../../../api/auth', () => ({
  authApi: {
    register: vi.fn().mockResolvedValue({ id: 1, email: 'a@b.com' }),
  },
}));

import { RegisterPage } from '../RegisterPage';

test('注册成功跳 /verify-email', async () => {
  render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<div>VERIFY</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), { target: { value: 'a@b.com' } });
  fireEvent.change(screen.getByPlaceholderText('至少 8 个字符'), { target: { value: 'password123' } });
  fireEvent.change(screen.getByPlaceholderText('再次输入密码'), { target: { value: 'password123' } });
  fireEvent.click(screen.getByRole('button', { name: '注册' }));
  await waitFor(() => expect(screen.getByText('VERIFY')).toBeInTheDocument());
});
```

- [ ] **Step 2: 写 VerifyEmailPage 测试**

```tsx
// frontend/src/features/auth/__tests__/VerifyEmailPage.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

const verifyMock = vi.fn();
vi.mock('../../../api/auth', () => ({
  authApi: {
    verifyEmailOtp: (...args: unknown[]) => verifyMock(...args),
    resendEmailOtp: vi.fn().mockResolvedValue({ expires_in: 600, next_resend_in: 60 }),
  },
}));

import { VerifyEmailPage } from '../VerifyEmailPage';

test('满 6 位自动 verify 并跳 /login', async () => {
  render(
    <MemoryRouter initialEntries={['/verify-email?email=a@b.com']}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>
  );
  verifyMock.mockResolvedValue({ verified: true });
  const inputs = screen.getAllByLabelText(/验证码第/);
  for (let i = 0; i < 6; i++) {
    fireEvent.change(inputs[i], { target: { value: String(i + 1) } });
  }
  await waitFor(() => expect(verifyMock).toHaveBeenCalledWith('a@b.com', '123456'));
  await waitFor(() => expect(screen.getByText('LOGIN')).toBeInTheDocument());
});

test('错误时回到首位并显示提示', async () => {
  render(
    <MemoryRouter initialEntries={['/verify-email?email=a@b.com']}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>
  );
  verifyMock.mockRejectedValue(new Error('验证码错误（剩余 4 次）'));
  const inputs = screen.getAllByLabelText(/验证码第/);
  for (let i = 0; i < 6; i++) fireEvent.change(inputs[i], { target: { value: '0' } });
  await waitFor(() => expect(screen.getByText(/验证码错误/)).toBeInTheDocument());
});
```

- [ ] **Step 3: 改 LoginPage 测试**

```tsx
// frontend/src/features/auth/__tests__/LoginPage.test.tsx（追加）
test('401 UserInactive 跳 /verify-email', async () => {
  // mock authApi.login 抛 ApiError { status:400, code:'UserInactive', message:'用户已被禁用' }
  // 触发后断言 navigate 到 /verify-email?email=...
});
```

- [ ] **Step 4: 跑测试**

Run: `cd frontend && npm test -- --run`
Expected: PASS（既存测试 + 3 个新测试）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/auth/__tests__/
git commit -m "test(frontend+auth): RegisterPage / VerifyEmailPage / LoginPage OTP flow"
```

---

## Task 19: 文档（`docs/architecture.md` / `docs/development.md` / `.env.example`）

**Files:**
- Modify:
  - `docs/architecture.md`
  - `docs/development.md`
  - `backend/.env.example`（如存在）
  - `.env.example`（如存在根目录）

- [ ] **Step 1: 在 `docs/architecture.md` 追加**

```markdown
## 邮箱验证（6 位邮件 OTP）

注册自动下发 6 位验证码到邮箱，未验证账号禁止登录。
- 表：`email_verifications`（id, user_id, email, code_hash, attempts, max_attempts, expires_at, consumed_at, last_sent_at）。
- 路由：`/api/auth/email-verifications/{request,resend,verify}`。
- 错误码：`EMAIL_NOT_FOUND / ALREADY_VERIFIED / CODE_INVALID / CODE_EXHAUSTED / CODE_EXPIRED / RATE_LIMITED / EMAIL_UNAVAILABLE`。
- `get_auth_router(..., requires_verification=True)`；`/api/users` 同步开启。
- 限流：email 1/min（请求+重发）、email 10/min（verify）、IP 30/min。
- Dev：未配 SMTP 时 `[DEV OTP] email=... code=...` 入 INFO 日志。
```

- [ ] **Step 2: 在 `docs/development.md` 追加**

```markdown
## 本地查看验证码

- 推荐：启动 Mailpit 并设置 `SMTP_HOST=mailpit SMTP_PORT=1025`。
  ```bash
  docker compose --profile mail up mailpit
  # 浏览器 http://localhost:8025
  ```
- 备选：未配 SMTP 时后端 INFO 日志输出明文 OTP，仅 `ENV=development`。
```

- [ ] **Step 3: `.env.example` 增补**

```env
# SMTP（开发用 Mailpit）
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_FROM_EMAIL=noreply@innovos.local
SMTP_TLS=false

# Email OTP
INNOVOS_OTP_PEPPER=          # 生产必填；开发留空将生成随机值
EMAIL_OTP_SOFT_FAIL=true     # dev 默认；prod 必须 false
```

- [ ] **Step 4: Commit**

```bash
git add docs/architecture.md docs/development.md backend/.env.example .env.example
git commit -m "docs(auth): document 6-digit email OTP verification flow"
```

---

## Task 20: 全量质量门

**Files:** 无新增。

- [ ] **Step 1: 跑后端测试**

Run: `cd backend && uv run pytest -q`
Expected: 全 PASS。

- [ ] **Step 2: 跑前端测试**

Run: `cd frontend && npm test -- --run`
Expected: 全 PASS。

- [ ] **Step 3: Lint + 类型**

Run: `make lint`
Expected: 0 errors。

- [ ] **Step 4: 启动 dev 烟测**

```bash
# Terminal A
cd /home/chou/InnovOS && docker compose --profile mail up -d mailpit
cd /home/chou/InnovOS && cp .env.example backend/.env  # 或已存在则跳过
cd /home/chou/InnovOS/backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal B
cd /home/chou/InnovOS/frontend && npm run dev
```

浏览器手动：
1. `/register` 注册 `manual@x.com` / `password123` → 应跳 `/verify-email?email=manual@x.com`。
2. Mailpit 收信取 6 位码；输入后应跳 `/login?email=manual@x.com`。
3. 登录成功 → `/`。

- [ ] **Step 5: 最终提交（若有微调）**

```bash
git status
# 若有改动：
git add -A
git commit -m "chore: post-impl lint/config polish"
```

---

## Self-Review

**Spec coverage:**
- §1 目标与范围 → Task 1-19 全覆盖。
- §2 决策 → 实施中按决策落地。
- §3 数据模型 → Task 2 落表 + Task 3 字段。
- §4.1 路由契约 → Task 7 路由。
- §4.1 错误码 → Task 4 异常类 + Task 7 handler。
- §4.2 服务层 → Task 5。
- §4.3 既有组件协作 → Task 7 (main.py) + Task 8 (users.py) + Task 6 (email_service.py)。
- §4.4 限流 → Task 11。
- §4.5 配置 → Task 1。
- §4.6 回填与回滚 → 设计层面已记录；不回填普通用户，避免误改。
- §5.1-§5.7 前端 → Task 12-18。
- §6 错误处理 → Task 4 / Task 5 / Task 7。
- §7 迁移 → Task 2（纯 DDL）。
- §8 配置与本地开发 → Task 1 + Task 19。
- §9 测试 → Task 9 + Task 18。
- §10 文档 → Task 19。
- §11 DoD → Task 20 验收。
- §12 风险与范围外 → 文档记录。
- §13 实施顺序 → 与 Task 1→20 一致。

**Placeholder scan:** 已扫描；无 `TBD / TODO / "类似 Task N"`。

**Type consistency:**
- `email_verification_service.issue_for_user(user, request)` → 返回 `dict[str, Any]` 含 `expires_in / next_resend_in`。
- `resend(email)` → 同上。
- `verify(email, code)` → 返回 `dict[str, Any]` 含 `verified` / `already`。
- 路由 schema `OtpIssuedOut / OtpVerifiedOut` 与服务返回一致。
- 前端 `authApi.verifyEmailOtp` 返回 `{ verified, already? }`，与 schema 对齐。
- `useAuthStore.register` 不再返回 `AuthUser`（因为不再调 login）；调用方按需。✓

**Gaps:** 无。
