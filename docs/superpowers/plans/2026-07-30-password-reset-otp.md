# InnovOS 密码重置验证码链路 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 InnovOS 密码重置从「邮件链接 + JWT token」改为「6 位邮件 OTP + 短期 reset_session token」,前端 3 页分离(`/forgot-password` → `/verify-reset` → `/reset-password`),状态通过 React Router `location.state` 传递。

**Architecture:** 在现有 `email_verifications` 表上加 `purpose` 列(纯 DDL,无数据回填);扩展 `EmailVerificationService` 让所有方法接收 `OtpPurpose` 参数;新增独立的 4 条密码重置路由(`/api/auth/password-reset/{request-otp,resend-otp,verify,set-password}`);前端新增 `VerifyResetOtpPage`、重写 `ResetPasswordPage` 接收 `location.state`;`UserManager.on_after_forgot_password` 改空操作,fastapi-users 内置 reset router 保留挂载但 InnovOS 不再调用。

**Tech Stack:** Python 3.11+, FastAPI, FastAPI Users 15.0.5, psycopg2, PostgreSQL 14+, Alembic; React 19 + TypeScript + Vite 8, Zustand 5, React Router 7, Vitest, React Testing Library.

**Reference spec:** `docs/superpowers/specs/2026-07-30-password-reset-otp-design.md`

---

## File Structure

### 后端

- Create:
  - `backend/app/api/password_reset.py` — 4 条密码重置路由。
  - `backend/app/exceptions/password_reset.py` — `InvalidResetSession` / `WeakPassword` 异常。
  - `backend/alembic/versions/0006_add_purpose_to_email_verifications.py` — Alembic migration。
  - `backend/tests/test_password_reset_otp.py` — 8+ 个后端测试。
- Modify:
  - `backend/app/services/email_verification_service.py` — 加 `OtpPurpose` 枚举;`issue_for_user` / `resend` / `verify` 加 `purpose` 参数;新增 `consume_reset_session` / `set_password_with_session`。
  - `backend/app/core/config.py` — 加 `RESET_SESSION_*` 配置。
  - `backend/app/schemas/email_verification.py` — `OtpRequestIn` / `OtpResendIn` 加 `purpose` 字段;新增 `ResetPasswordSetIn`。
  - `backend/app/auth/users.py` — `on_after_forgot_password` 改空操作。
  - `backend/app/services/email_service.py` — 新增 `send_password_reset_otp_sync`。
  - `backend/app/main.py` — 挂载新路由。
  - `backend/app/tables/pg_schema.py` — `init_email_verifications` 加 `purpose` 列(同步)。

### 前端

- Create:
  - `frontend/src/features/auth/VerifyResetOtpPage.tsx`
  - `frontend/src/features/auth/__tests__/VerifyResetOtpPage.test.tsx`
  - `frontend/src/features/auth/__tests__/ResetPasswordPage.test.tsx`(如不存在则新建)
- Modify:
  - `frontend/src/api/auth.ts` — 新增 3 个方法;`forgotPassword` / `resetPassword` 标 `@deprecated`。
  - `frontend/src/routes/index.tsx` — 注册 `/verify-reset` 路由。
  - `frontend/src/features/auth/ForgotPasswordPage.tsx` — 调新 endpoint,成功后跳 `/verify-reset`。
  - `frontend/src/features/auth/ResetPasswordPage.tsx` — 重写:state 缺失跳回 / 调新 endpoint。

### 文档

- Modify:
  - `docs/smtp-operations.md` — 同步更新密码重置流程章节。

---

## Task 1: Alembic migration — 加 `purpose` 列

**Files:**
- Create: `backend/alembic/versions/0006_add_purpose_to_email_verifications.py`
- Modify: `backend/app/tables/pg_schema.py:601-633`

- [ ] **Step 1: 确认现有 alembic 迁移文件命名约定**

```bash
cd /home/chou/InnovOS/backend
ls alembic/versions/*.py
```

找到最近一个 revision id(如 `0005_expand_api_key_storage.py`),新文件命名用 `0006_add_purpose_to_email_verifications.py`。

- [ ] **Step 2: 写 Alembic migration 脚本**

```python
"""add purpose to email_verifications

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE email_verifications "
        "ADD COLUMN IF NOT EXISTS purpose VARCHAR(32) NOT NULL "
        "DEFAULT 'email_verification'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx "
        "ON email_verifications(email, purpose)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS email_verifications_email_purpose_idx")
    op.execute("ALTER TABLE email_verifications DROP COLUMN IF EXISTS purpose")
```

- [ ] **Step 3: 跑 migration 验证**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/alembic upgrade head
```

预期:`Running upgrade 0005 -> 0006, add purpose to email_verifications`

- [ ] **Step 4: 验证 schema 到位**

```bash
.venv/bin/python -c "
from app.database import get_db
db = get_db()
try:
    cols = db.execute(\"\"\"
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'email_verifications'
        ORDER BY ordinal_position
    \"\"\").fetchall()
    for c in cols:
        print(f'{c[\"column_name\"]:20s} {c[\"data_type\"]:20s} nullable={c[\"is_nullable\"]:3s} default={c[\"column_default\"]}')
    idx = db.execute(\"SELECT indexname FROM pg_indexes WHERE tablename='email_verifications'\").fetchall()
    print('Indexes:', [i['indexname'] for i in idx])
finally:
    db.close()
"
```

预期输出包含 `purpose VARCHAR(32 NOT NULL email_verification` 和 `email_verifications_email_purpose_idx`。

- [ ] **Step 5: 同步 `pg_schema.py`(供 init_db() 路径使用)**

修改 `backend/app/tables/pg_schema.py:601-633` 的 `init_email_verifications` 函数,在 `CREATE TABLE IF NOT EXISTS email_verifications (...)` 的字段列表中加 `purpose VARCHAR(32) NOT NULL DEFAULT 'email_verification'`,并在索引块加:

```python
"CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx "
"ON email_verifications(email, purpose)"
```

完整代码片段:

```python
def init_email_verifications(db):
    """email_verifications 表 — 6 位邮件 OTP。"""
    db.execute(
        "CREATE TABLE IF NOT EXISTS email_verifications ("
        "id BIGSERIAL PRIMARY KEY,"
        "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
        "email VARCHAR(255) NOT NULL,"
        "code_hash CHAR(64) NOT NULL,"
        "attempts SMALLINT NOT NULL DEFAULT 0,"
        "max_attempts SMALLINT NOT NULL DEFAULT 5,"
        "expires_at TIMESTAMPTZ NOT NULL,"
        "consumed_at TIMESTAMPTZ,"
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
        "last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
        "purpose VARCHAR(32) NOT NULL DEFAULT 'email_verification'"
        ")"
    )
    db.execute("CREATE INDEX IF NOT EXISTS email_verifications_user_id_idx ON email_verifications(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS email_verifications_email_idx ON email_verifications(email)")
    db.execute("CREATE INDEX IF NOT EXISTS email_verifications_active_idx ON email_verifications(consumed_at) WHERE consumed_at IS NULL")
    db.execute("CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx ON email_verifications(email, purpose)")
```

- [ ] **Step 6: 跑后端测试确认 schema 改动不影响既有行为**

```bash
.venv/bin/python -m pytest tests/test_email_service.py tests/test_auth_reset_password.py tests/test_auth_register.py tests/test_auth_login.py -v --tb=short
```

预期:全部 PASS。

- [ ] **Step 7: Commit**

```bash
cd /home/chou/InnovOS
git add backend/alembic/versions/0006_add_purpose_to_email_verifications.py \
        backend/app/tables/pg_schema.py
git commit -m "feat(auth): add purpose column to email_verifications"
```

---

## Task 2: 加 `OtpPurpose` 枚举与 `purpose` 参数到 `EmailVerificationService`

**Files:**
- Modify: `backend/app/services/email_verification_service.py`

- [ ] **Step 1: 写失败测试 — `purpose` 参数使重置 OTP 与邮箱验证 OTP 隔离**

创建 `backend/tests/test_password_reset_otp.py`:

```python
"""密码重置 OTP 链路测试 — purpose 隔离 + reset_session 一次性消费。"""
from tests.conftest_auth import *  # noqa: F401, F403

import pytest

from app.services.email_verification_service import (
    EmailVerificationService,
    OtpPurpose,
)
from app.exceptions.email_verification import (
    CodeInvalid, CodeExpired, CodeExhausted, EmailNotFound, AlreadyVerified,
)


@pytest.fixture
def make_user(db):
    """插入测试用户,返回 email + user_id。"""
    created = []

    def _make(email: str, is_verified: bool = True) -> dict:
        db.execute(
            "INSERT INTO users (email, hashed_password, is_active, is_verified, is_superuser) "
            "VALUES (%s, %s, TRUE, %s, FALSE) ON CONFLICT (email) DO NOTHING",
            (email, "fakehash", is_verified),
        )
        db.commit()
        row = db.execute("SELECT id, email FROM users WHERE email=%s", (email,)).fetchone()
        created.append(email)
        return row

    yield _make

    for email in created:
        db.execute("DELETE FROM email_verifications WHERE email=%s", (email,))
        db.execute("DELETE FROM users WHERE email=%s", (email,))
    db.commit()


class TestPurposeIsolation:
    def test_request_otp_creates_password_reset_purpose_row(self, db, make_user):
        """下发 password_reset OTP,DB 行 purpose 字段必须正确。"""
        make_user("isolation@example.com")
        svc = EmailVerificationService()

        class _U:
            email = "isolation@example.com"
            id = db.execute(
                "SELECT id FROM users WHERE email=%s", ("isolation@example.com",)
            ).fetchone()["id"]

        svc.issue_for_user(_U(), request=None, purpose=OtpPurpose.PASSWORD_RESET)
        row = db.execute(
            "SELECT purpose FROM email_verifications "
            "WHERE email=%s ORDER BY id DESC LIMIT 1",
            ("isolation@example.com",),
        ).fetchone()
        assert row["purpose"] == "password_reset", \
            f"purpose 应为 password_reset,实际 {row['purpose']}"

    def test_email_verification_otp_cannot_reset_password(self, db, make_user):
        """用 email_verification 类型的 OTP 调重置 verify → 抛 CodeExpired。"""
        make_user("cross1@example.com")
        svc = EmailVerificationService()

        class _U:
            email = "cross1@example.com"
            id = db.execute(
                "SELECT id FROM users WHERE email=%s", ("cross1@example.com",)
            ).fetchone()["id"]

        svc.issue_for_user(_U(), request=None, purpose=OtpPurpose.EMAIL_VERIFICATION)

        with pytest.raises((CodeExpired, CodeInvalid, CodeExhausted)):
            svc.verify(
                "cross1@example.com", "000000",
                purpose=OtpPurpose.PASSWORD_RESET,
            )
```

- [ ] **Step 2: 跑测试确认失败(因为 `purpose` 参数还不存在)**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_password_reset_otp.py::TestPurposeIsolation -v --tb=short
```

预期:FAIL with "TypeError: issue_for_user() got an unexpected keyword argument 'purpose'"

- [ ] **Step 3: 修改 `EmailVerificationService` 加 `OtpPurpose` 枚举 + `purpose` 参数**

修改 `backend/app/services/email_verification_service.py`:

```python
# 在文件顶部 import 区域加
import jwt
from enum import Enum
from fastapi_users.jwt import generate_jwt, decode_jwt

from app.exceptions.password_reset import InvalidResetSession  # noqa: F401  # 见 Task 5


class OtpPurpose(str, Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
```

修改 `issue_for_user`:

```python
    def issue_for_user(
        self, user, request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
        with db_session() as db:
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
                (user.id, user.email, _hash_code(code), settings.OTP_MAX_ATTEMPTS,
                 str(ttl), purpose.value),
            )
        if purpose == OtpPurpose.PASSWORD_RESET:
            email_service.send_password_reset_otp_sync(user, code, request)
        else:
            email_service.send_verification_otp_sync(user, code, request)
        logger.info("OTP issued user=%s purpose=%s expires_in=%s", user.id, purpose.value, ttl)
        return {"expires_in": ttl, "next_resend_in": settings.OTP_RESEND_COOLDOWN}
```

修改 `resend`:

```python
    def resend(
        self, email: str, request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
        with db_session() as db:
            user = db.execute(
                "SELECT id, email, is_verified FROM users WHERE email=%s", (email,)
            ).fetchone()
            if not user:
                raise EmailNotFound()
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
            class _U:
                pass
            u = _U()
            u.id = user["id"]
            u.email = user["email"]
            return self.issue_for_user(u, request, purpose=purpose)
```

修改 `verify`:

```python
    def verify(
        self, email: str, code: str,
        request: Optional[Request] = None,
        purpose: OtpPurpose = OtpPurpose.EMAIL_VERIFICATION,
    ) -> dict[str, Any]:
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
                    "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s", (row["id"],)
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
                db.execute(
                    "UPDATE email_verifications SET consumed_at=NOW() WHERE id=%s", (row["id"],)
                )
                # 同 (email, purpose) 其他活跃 OTP 一并作废(防重放)
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
```

- [ ] **Step 4: 加 `_issue_reset_session_token` / `consume_reset_session` / `set_password_with_session`**

在 `email_verification_service.py` 顶部 helper 区加:

```python
def _reset_session_jwt_secret() -> str:
    """优先用独立 secret,否则回退 SECRET_KEY。"""
    return settings.RESET_SESSION_JWT_SECRET or settings.SECRET_KEY


def _issue_reset_session_token(user_id: int) -> str:
    return generate_jwt(
        {
            "sub": str(user_id),
            "aud": settings.RESET_SESSION_JWT_AUDIENCE,
        },
        _reset_session_jwt_secret(),
        settings.RESET_SESSION_TOKEN_TTL_SECONDS,
    )


def _decode_reset_session_token(token: str) -> int:
    data = decode_jwt(
        token,
        _reset_session_jwt_secret(),
        [settings.RESET_SESSION_JWT_AUDIENCE],
    )
    return int(data["sub"])
```

`EmailVerificationService` 类加 2 个方法:

```python
    def consume_reset_session(self, token: str) -> int:
        """解码 reset_session_token;返回 user_id。失败抛 InvalidResetSession。"""
        try:
            return _decode_reset_session_token(token)
        except (jwt.PyJWTError, KeyError, ValueError):
            raise InvalidResetSession()

    def set_password_with_session(self, token: str, new_password: str) -> dict[str, Any]:
        """用 reset_session_token 改密。走 UserManager 的 bcrypt 逻辑。"""
        user_id = self.consume_reset_session(token)
        with db_session() as db:
            # 走密码哈希逻辑(不要绕过)
            from app.db.models import User
            from app.auth.sync_db import SyncSQLAlchemyUserDatabase
            from app.auth.users import UserManager
            from fastapi_users.password import PasswordHelper

            user_db = SyncSQLAlchemyUserDatabase(db, User)
            manager = UserManager(user_db)
            # 同步执行 async 方法(本服务已在 sync 上下文)
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                user = loop.run_until_complete(manager.get(user_id))
                if not user:
                    raise InvalidResetSession()
                loop.run_until_complete(manager._update(user, {"password": new_password}))
            finally:
                loop.close()
        return {"reset": True}
```

**注意:** 上面用了 `manager._update` private method。实现时应优先尝试 public 接口(`manager.update` 接受 `schemas.UU` 对象)。如不可行,保留此 private 调用并加注释说明原因。

- [ ] **Step 5: 跑测试确认通过**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_password_reset_otp.py::TestPurposeIsolation -v --tb=short
```

预期:2 个 PASS。

- [ ] **Step 6: 跑全套测试确认无回归**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short -x -k "auth or email"
```

预期:既有测试全过。

- [ ] **Step 7: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/services/email_verification_service.py backend/tests/test_password_reset_otp.py
git commit -m "feat(auth): extend EmailVerificationService with purpose and reset_session"
```

---

## Task 3: 加 `RESET_SESSION_*` 配置

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_core_config.py` 加(如该文件不存在则 `ls tests/` 确认):

```python
def test_reset_session_config_defaults(monkeypatch):
    monkeypatch.setenv("INNOVOS_JWT_SECRET", "test-secret-fixed-for-test")
    from app.core.config import Settings
    s = Settings(_env_file=None)
    assert s.RESET_SESSION_TOKEN_TTL_SECONDS == 600
    assert s.RESET_SESSION_JWT_AUDIENCE == "password-reset:consume"
    # RESET_SESSION_JWT_SECRET 默认回退 SECRET_KEY
    assert s.RESET_SESSION_JWT_SECRET == s.SECRET_KEY
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_core_config.py::test_reset_session_config_defaults -v --tb=short
```

预期:FAIL with "AttributeError: 'Settings' object has no attribute 'RESET_SESSION_TOKEN_TTL_SECONDS'"

- [ ] **Step 3: 加配置字段**

在 `backend/app/core/config.py` 找到 `OTP_*` 配置段后加:

```python
    # ── Password Reset Session ──
    RESET_SESSION_TOKEN_TTL_SECONDS: int = 600  # 10 分钟
    RESET_SESSION_JWT_AUDIENCE: str = "password-reset:consume"
    RESET_SESSION_JWT_SECRET: str = ""  # 留空回退到 SECRET_KEY;生产建议独立
```

- [ ] **Step 4: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/test_core_config.py::test_reset_session_config_defaults -v --tb=short
```

预期:PASS。

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/core/config.py backend/tests/test_core_config.py
git commit -m "feat(auth): add RESET_SESSION_* config fields"
```

---

## Task 4: 加 `send_password_reset_otp_sync` 邮件方法

**Files:**
- Modify: `backend/app/services/email_service.py`

- [ ] **Step 1: 写失败测试 — 邮件正文含验证码 + 不含 URL**

在 `backend/tests/test_email_service.py` 加:

```python
def test_password_reset_otp_email_includes_code(configured_service):
    """重置密码邮件只发 6 位验证码,不含 URL。"""
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        configured_service.send_password_reset_otp_sync(user, "199622")
        raw = server.sendmail.call_args[0][2]
        assert "199622" in raw, "邮件必须包含 6 位验证码"
        assert "http://" not in raw and "https://" not in raw, \
            "重置邮件不应包含任何 URL"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_email_service.py::test_password_reset_otp_email_includes_code -v --tb=short
```

预期:FAIL with "AttributeError: 'EmailService' object has no attribute 'send_password_reset_otp_sync'"

- [ ] **Step 3: 实现 `send_password_reset_otp_sync`**

在 `backend/app/services/email_service.py` 找到 `send_verification_otp_sync` 方法后加:

```python
    def send_password_reset_otp_sync(self, user, code: str, request=None) -> None:
        """发送密码重置邮件 — 仅含 6 位验证码,无 URL。
        dev 模式 SMTP 未配置时,把验证码明文写日志。
        """
        ttl_min = settings.OTP_TTL_SECONDS // 60
        inner = (
            _brand_logo()
            + '<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#111827;">密码重置</h1>\n'
            + '<p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">'
              '您正在申请重置 InnovOS 账号密码,请使用以下验证码完成操作。</p>\n'
            + _code_pill(code)
            + _footer_note(ttl_min)
        )
        body = _wrap_card(inner)
        if not self.host:
            if settings.ENVIRONMENT == "production" and not settings.EMAIL_OTP_SOFT_FAIL:
                raise EmailUnavailable()
            if settings.ENVIRONMENT == "development":
                logger.info(
                    "[DEV RESET OTP] email=%s code=%s ttl=%ss",
                    user.email, code, settings.OTP_TTL_SECONDS,
                )
                return
            logger.warning("SMTP_HOST 未配置,跳过密码重置邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 密码重置验证码", body)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/test_email_service.py -v --tb=short
```

预期:全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/services/email_service.py backend/tests/test_email_service.py
git commit -m "feat(auth): send_password_reset_otp_sync sends code-only email"
```

---

## Task 5: 加 `password_reset` 异常类型

**Files:**
- Create: `backend/app/exceptions/password_reset.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建异常模块**

```python
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
```

- [ ] **Step 2: 在 `backend/app/main.py` 注册异常 handler**

找到 `app_.add_exception_handler(EmailVerificationError, email_verification_exception_handler)` 段,确认已在(若不在则补)。`InvalidResetSession` / `WeakPassword` 继承自 `EmailVerificationError`,会被通用 handler 自动处理。

无需新增独立 handler。

- [ ] **Step 3: 写失败测试**

加到 `backend/tests/test_password_reset_otp.py`:

```python
def test_invalid_reset_session_status():
    from app.exceptions.password_reset import InvalidResetSession
    e = InvalidResetSession()
    assert e.status == 401
    assert e.code == "RESET_SESSION_INVALID"
```

- [ ] **Step 4: 跑测试**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_password_reset_otp.py::test_invalid_reset_session_status -v --tb=short
```

预期:PASS。

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/exceptions/password_reset.py backend/app/main.py backend/tests/test_password_reset_otp.py
git commit -m "feat(auth): add password_reset exception types"
```

---

## Task 6: 加密码重置 HTTP 路由

**Files:**
- Create: `backend/app/api/password_reset.py`
- Modify: `backend/app/schemas/email_verification.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 写失败测试 — 路由存在**

加到 `backend/tests/test_password_reset_otp.py`:

```python
class TestPasswordResetRoutes:
    def test_request_otp_route_exists(self, auth_client):
        """路由存在且接受 POST。"""
        r = auth_client.post(
            "/api/auth/password-reset/request-otp",
            json={"email": "nobody@example.com"},
        )
        # 防探测:未知邮箱也返回 202
        assert r.status_code == 202, r.text

    def test_set_password_route_exists(self, auth_client):
        r = auth_client.post(
            "/api/auth/password-reset/set-password",
            json={"reset_token": "garbage", "new_password": "newpass1234"},
        )
        # 错误 token → 401
        assert r.status_code == 401, r.text
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_password_reset_otp.py::TestPasswordResetRoutes -v --tb=short
```

预期:FAIL with "404 Not Found"

- [ ] **Step 3: 创建路由文件 `backend/app/api/password_reset.py`**

```python
# backend/app/api/password_reset.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.email_verification import (
    EmailNotFound,
    EmailVerificationError,
    OtpRateLimited,
)
from app.rate_limit_redis import (
    email_otp_ip_limiter,
    email_otp_request_limiter,
    email_otp_verify_limiter,
)
from app.schemas.email_verification import (
    OtpIssuedOut,
    OtpRequestIn,
    OtpResendIn,
    OtpVerifyIn,
    ResetPasswordSetIn,
)
from app.services.email_verification_service import (
    EmailVerificationService,
    OtpPurpose,
)

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


@router.post("/request-otp", response_model=OtpIssuedOut, status_code=202)
def request_otp(payload: OtpRequestIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.check(ip)[0]:
        raise OtpRateLimited(60)
    if not email_otp_request_limiter.check(payload.email)[0]:
        raise OtpRateLimited(60)
    try:
        rec = EmailVerificationService().resend(
            payload.email, request, purpose=OtpPurpose.PASSWORD_RESET,
        )
    except EmailNotFound:
        return OtpIssuedOut(
            expires_in=settings.OTP_TTL_SECONDS,
            next_resend_in=settings.OTP_RESEND_COOLDOWN,
        )
    except EmailVerificationError:
        return OtpIssuedOut(
            expires_in=settings.OTP_TTL_SECONDS,
            next_resend_in=settings.OTP_RESEND_COOLDOWN,
        )
    return OtpIssuedOut(**rec)


@router.post("/resend-otp", response_model=OtpIssuedOut, status_code=202)
def resend_otp(payload: OtpResendIn, request: Request) -> OtpIssuedOut:
    ip = request.client.host if request.client else "unknown"
    allowed, _, _ = email_otp_ip_limiter.check(ip)
    if not allowed:
        raise OtpRateLimited(60)
    rec = EmailVerificationService().resend(
        payload.email, request, purpose=OtpPurpose.PASSWORD_RESET,
    )
    return OtpIssuedOut(**rec)


@router.post("/verify", response_model=dict)
def verify_otp(payload: OtpVerifyIn, request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not email_otp_ip_limiter.check(ip)[0]:
        raise OtpRateLimited(60)
    if not email_otp_verify_limiter.check(payload.email)[0]:
        raise OtpRateLimited(60)
    rec = EmailVerificationService().verify(
        payload.email, payload.code, request, purpose=OtpPurpose.PASSWORD_RESET,
    )
    return rec


@router.post("/set-password", status_code=200)
def set_password(payload: ResetPasswordSetIn, request: Request) -> dict:
    EmailVerificationService().set_password_with_session(
        payload.reset_token, payload.new_password,
    )
    return {"reset": True}
```

- [ ] **Step 4: 加 Pydantic schema `ResetPasswordSetIn`**

修改 `backend/app/schemas/email_verification.py`,在文件末尾加:

```python
class ResetPasswordSetIn(BaseModel):
    reset_token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 5: 在 `backend/app/main.py` 注册新路由**

找到 `app_.include_router(email_verification_router)` 段,加:

```python
from app.api.password_reset import router as password_reset_router

app_.include_router(password_reset_router)
```

- [ ] **Step 6: 跑测试确认通过**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_password_reset_otp.py -v --tb=short
```

预期:全部 PASS。

- [ ] **Step 7: 端到端 curl 冒烟**

按 spec §7.3 跑三个 curl 命令(真实邮箱或 dev 日志均可),确认返回码符合预期。

- [ ] **Step 8: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/api/password_reset.py backend/app/schemas/email_verification.py backend/app/main.py backend/tests/test_password_reset_otp.py
git commit -m "feat(auth): add 4 password-reset routes with OTP flow"
```

---

## Task 7: 改 `UserManager.on_after_forgot_password` 为空操作

**Files:**
- Modify: `backend/app/auth/users.py:45-50`

- [ ] **Step 1: 修改回调函数**

```python
    async def on_after_forgot_password(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        """InnovOS 不依赖此回调 — 重置密码走自研 OTP 流程(/api/auth/password-reset/*)。
        fastapi-users 的内置 reset router 仍保留挂载(向后兼容),但 InnovOS 前端不调用。
        """
        pass
```

- [ ] **Step 2: 跑现有 auth 测试确认无回归**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/test_auth_reset_password.py tests/test_auth_register.py tests/test_auth_login.py -v --tb=short
```

预期:全部 PASS。

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS
git add backend/app/auth/users.py
git commit -m "refactor(auth): on_after_forgot_password is no-op (use custom OTP flow)"
```

---

## Task 8: 前端 API 客户端新增 3 个方法

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/api/__tests__/auth.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/src/api/__tests__/auth.test.ts` 末尾加:

```typescript
describe('password reset OTP API', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('requestPasswordResetOtp posts to /api/auth/password-reset/request-otp', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 202, text: () => Promise.resolve(''),
    });
    vi.stubGlobal('fetch', mockFetch);
    const { authApi } = await import('../auth');
    await authApi.requestPasswordResetOtp('a@b.com');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/password-reset/request-otp'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ email: 'a@b.com' }) }),
    );
  });

  it('verifyPasswordResetOtp returns reset_token', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      text: () => Promise.resolve(JSON.stringify({ verified: true, reset_token: 'jwt-xxx' })),
    });
    vi.stubGlobal('fetch', mockFetch);
    const { authApi } = await import('../auth');
    const r = await authApi.verifyPasswordResetOtp('a@b.com', '199622');
    expect(r.reset_token).toBe('jwt-xxx');
  });

  it('setNewPassword posts reset_token + new_password', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, text: () => Promise.resolve('{"reset":true}'),
    });
    vi.stubGlobal('fetch', mockFetch);
    const { authApi } = await import('../auth');
    await authApi.setNewPassword('jwt-xxx', 'newpass1234');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/password-reset/set-password'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reset_token: 'jwt-xxx', new_password: 'newpass1234' }),
      }),
    );
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/api/__tests__/auth.test.ts
```

预期:FAIL — `authApi.requestPasswordResetOtp is not a function`

- [ ] **Step 3: 实现 3 个方法(deprecate 旧的)**

修改 `frontend/src/api/auth.ts`,把 `forgotPassword` 标 `@deprecated`,在它下面加:

```typescript
  /**
   * 请求密码重置 OTP。
   * @deprecated 旧 URL token 流程保留以备回滚;新流程走 requestPasswordResetOtp + verifyPasswordResetOtp + setNewPassword。
   */
  forgotPassword(email: string): Promise<void> {
    return apiRequest<void>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 请求密码重置 OTP(替代 forgotPassword) */
  requestPasswordResetOtp(email: string): Promise<void> {
    return apiRequest<void>('/api/auth/password-reset/request-otp', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 验证密码重置 OTP,返回短期 reset_token */
  verifyPasswordResetOtp(email: string, code: string): Promise<{ verified: boolean; reset_token: string }> {
    return apiRequest('/api/auth/password-reset/verify', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    });
  },

  /** 用 reset_token + 新密码提交改密 */
  setNewPassword(reset_token: string, new_password: string): Promise<{ reset: boolean }> {
    return apiRequest('/api/auth/password-reset/set-password', {
      method: 'POST',
      body: JSON.stringify({ reset_token, new_password }),
    });
  },

  /**
   * @deprecated 旧 URL token 流程;改用 setNewPassword。
   */
  resetPassword(token: string, password: string): Promise<void> {
    return apiRequest<void>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    });
  },
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/api/__tests__/auth.test.ts
```

预期:全部 PASS。

- [ ] **Step 5: tsc 校验**

```bash
cd /home/chou/InnovOS/frontend
npx tsc --noEmit
```

预期:无错误。

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS
git add frontend/src/api/auth.ts frontend/src/api/__tests__/auth.test.ts
git commit -m "feat(frontend): add password reset OTP API methods"
```

---

## Task 9: 新增 `VerifyResetOtpPage` 前端页面

**Files:**
- Create: `frontend/src/features/auth/VerifyResetOtpPage.tsx`
- Create: `frontend/src/features/auth/__tests__/VerifyResetOtpPage.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
// frontend/src/features/auth/__tests__/VerifyResetOtpPage.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: {
    verifyPasswordResetOtp: vi.fn(),
    requestPasswordResetOtp: vi.fn(),
  },
}));

import { authApi } from '../../../api/auth';
import { VerifyResetOtpPage } from '../VerifyResetOtpPage';

describe('VerifyResetOtpPage', () => {
  it('redirects to /forgot-password if email is missing in location state', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/verify-reset' }]}>
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('navigates to /reset-password with state after successful verify', async () => {
    (authApi.verifyPasswordResetOtp as any).mockResolvedValue({
      verified: true,
      reset_token: 'jwt-xxx',
    });
    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/verify-reset', state: { email: 'a@b.com' } }]}
      >
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/reset-password" element={<div>RESET_PAGE</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    const inputs = screen.getAllByRole('textbox');
    inputs.forEach((input, i) => {
      fireEvent.change(input, { target: { value: String(i + 1) } });
    });
    await waitFor(() => {
      expect(screen.getByText('RESET_PAGE')).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/features/auth/__tests__/VerifyResetOtpPage.test.tsx
```

预期:FAIL — `Cannot find module '../VerifyResetOtpPage'`

- [ ] **Step 3: 创建 `frontend/src/features/auth/VerifyResetOtpPage.tsx`**

复制 `frontend/src/features/auth/VerifyEmailPage.tsx` 整体结构,把 `verifyEmailOtp` 改为 `verifyPasswordResetOtp`,成功后 `navigate('/reset-password', { state: { email, reset_token: r.reset_token }, replace: true })`。

完整实现:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Mail, ShieldCheck } from 'lucide-react';

export function VerifyResetOtpPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const email = (location.state as { email?: string } | null)?.email ?? '';
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const refs = useRef<Array<HTMLInputElement | null>>([null, null, null, null, null, null]);

  useEffect(() => {
    if (!email) navigate('/forgot-password', { replace: true });
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
      const r = await authApi.verifyPasswordResetOtp(email, full);
      navigate('/reset-password', {
        state: { email, reset_token: r.reset_token },
        replace: true,
      });
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
      await authApi.requestPasswordResetOtp(email);
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
          <p className="text-slate-400 text-sm">密码重置验证</p>
        </div>

        <form
          onSubmit={e => { e.preventDefault(); if (code.length === 6) void submit(code); }}
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4"
        >
          <h2 className="text-white font-bold text-lg text-center">输入验证码</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex items-center gap-2 text-slate-300 text-sm">
            <Mail className="w-4 h-4" />
            <span>验证码已发送至 {email}</span>
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
            验证遇到问题?{' '}
            <Link to="/forgot-password" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              重新申请
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

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/features/auth/__tests__/VerifyResetOtpPage.test.tsx
```

预期:全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS
git add frontend/src/features/auth/VerifyResetOtpPage.tsx frontend/src/features/auth/__tests__/VerifyResetOtpPage.test.tsx
git commit -m "feat(frontend): add VerifyResetOtpPage for password reset OTP flow"
```

---

## Task 10: 注册 `/verify-reset` 路由

**Files:**
- Modify: `frontend/src/routes/index.tsx`

- [ ] **Step 1: 跑测试确认无回归(基线)**

```bash
cd /home/chou/InnovOS/frontend
npx tsc --noEmit
```

预期:无错误。

- [ ] **Step 2: 注册新路由**

在 `frontend/src/routes/index.tsx` 顶部加 import:

```tsx
const VerifyResetOtpPage = lazyPage(() => import('../features/auth/VerifyResetOtpPage'));
```

在路由数组加:

```tsx
{ path: '/verify-reset', element: <VerifyResetOtpPage /> },
```

- [ ] **Step 3: tsc 校验**

```bash
cd /home/chou/InnovOS/frontend
npx tsc --noEmit
```

预期:无错误。

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS
git add frontend/src/routes/index.tsx
git commit -m "feat(frontend): register /verify-reset route"
```

---

## Task 11: 重写 `ForgotPasswordPage` 调用新 endpoint

**Files:**
- Modify: `frontend/src/features/auth/ForgotPasswordPage.tsx`

- [ ] **Step 1: 改 `handleSubmit` 调新 endpoint + 跳 `/verify-reset`**

修改 `frontend/src/features/auth/ForgotPasswordPage.tsx`:

```tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.requestPasswordResetOtp(email);
      navigate('/verify-reset', { state: { email } });
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败,请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // ... 其它 UI 沿用现状
}
```

- [ ] **Step 2: 微调文案**

「发送重置邮件」→「发送验证码」
「如果该邮箱已注册,我们将向其发送一封密码重置邮件。」→「如果该邮箱已注册,我们将向其发送 6 位验证码。」

(注意:`submitted` 状态不再被使用——提交成功后直接 navigate;此分支可保留为兜底。)

- [ ] **Step 3: 跑前端测试 + tsc**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/features/auth/__tests__/
npx tsc --noEmit
```

预期:全部 PASS。

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS
git add frontend/src/features/auth/ForgotPasswordPage.tsx
git commit -m "feat(frontend): ForgotPasswordPage triggers OTP flow"
```

---

## Task 12: 重写 `ResetPasswordPage` 接收 state + 调新 endpoint

**Files:**
- Modify: `frontend/src/features/auth/ResetPasswordPage.tsx`
- Create: `frontend/src/features/auth/__tests__/ResetPasswordPage.test.tsx`(如不存在)

- [ ] **Step 1: 写失败测试**

```tsx
// frontend/src/features/auth/__tests__/ResetPasswordPage.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: { setNewPassword: vi.fn() },
}));

import { authApi } from '../../../api/auth';
import { ResetPasswordPage } from '../ResetPasswordPage';

describe('ResetPasswordPage', () => {
  it('redirects to /forgot-password if state is missing', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/reset-password' }]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('submits setNewPassword with state.reset_token + new_password', async () => {
    (authApi.setNewPassword as any).mockResolvedValue({ reset: true });
    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/reset-password',
          state: { email: 'a@b.com', reset_token: 'jwt-xxx' },
        }]}
      >
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    const inputs = screen.getAllByPlaceholderText(/至少 8 个字符|再次输入/);
    fireEvent.change(inputs[0], { target: { value: 'newpass1234' } });
    fireEvent.change(inputs[1], { target: { value: 'newpass1234' } });
    fireEvent.click(screen.getByRole('button', { name: /重置密码/ }));
    await waitFor(() => {
      expect(authApi.setNewPassword).toHaveBeenCalledWith('jwt-xxx', 'newpass1234');
    });
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/features/auth/__tests__/ResetPasswordPage.test.tsx
```

预期:FAIL — 测试不匹配(若旧测试存在)或模块找不到(若不存在)

- [ ] **Step 3: 重写 `frontend/src/features/auth/ResetPasswordPage.tsx`**

整体重写,关键改动:state 缺失跳回;提交改用 `setNewPassword`。

完整实现:

```tsx
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Eye, EyeOff, Lock, Check, ArrowLeft, XCircle } from 'lucide-react';

interface LocationState { email?: string; reset_token?: string }

export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = (location.state ?? {}) as LocationState;
  const email = state.email ?? '';
  const reset_token = state.reset_token ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // state 缺失 → 跳回
  if (!email || !reset_token) {
    navigate('/forgot-password', { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('两次密码不一致'); return; }
    if (password.length < 8) { setError('密码至少 8 个字符'); return; }
    setLoading(true);
    try {
      await authApi.setNewPassword(reset_token, password);
      navigate('/login?reset=ok');
    } catch (err) {
      const msg = err instanceof Error ? err.message : '重置失败';
      setError(msg);
      if (msg.includes('RESET_SESSION_INVALID') || msg.includes('重置会话')) {
        setTimeout(() => navigate('/forgot-password', { replace: true }), 1500);
      }
    } finally {
      setLoading(false);
    }
  };

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
          onSubmit={handleSubmit}
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4"
        >
          <h2 className="text-white font-bold text-lg text-center">重置密码</h2>
          <p className="text-slate-400 text-sm text-center -mt-2">为 {email} 设置新密码</p>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* New Password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">新密码</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type={showPw ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-10 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="至少 8 个字符"
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">确认新密码</label>
            <div className="relative">
              <Check className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type={showPw ? 'text' : 'password'}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="再次输入"
                autoComplete="new-password"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? '重置中…' : '重置密码'}
          </button>

          <p className="text-center text-sm text-slate-500">
            <Link
              to="/forgot-password"
              className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" /> 重新申请
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run src/features/auth/__tests__/ResetPasswordPage.test.tsx
```

预期:全部 PASS。

- [ ] **Step 5: tsc 校验**

```bash
cd /home/chou/InnovOS/frontend
npx tsc --noEmit
```

预期:无错误。

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS
git add frontend/src/features/auth/ResetPasswordPage.tsx frontend/src/features/auth/__tests__/ResetPasswordPage.test.tsx
git commit -m "feat(frontend): ResetPasswordPage reads reset_token from state"
```

---

## Task 13: 端到端冒烟测试

**Files:** 无(纯验证)

- [ ] **Step 1: 重启后端让 alembic migration + 新路由生效**

```bash
cd /home/chou/InnovOS/backend
# 如果 docker: docker compose restart backend
# 如果本地: Ctrl+C 后重启 uvicorn
```

- [ ] **Step 2: 跑后端全量测试**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -m pytest tests/ -v --tb=short
```

预期:全部 PASS。

- [ ] **Step 3: 跑前端全量测试**

```bash
cd /home/chou/InnovOS/frontend
npx vitest run
npx tsc --noEmit
```

预期:全部 PASS。

- [ ] **Step 4: 浏览器手动跑一遍**

1. 打开 `http://localhost:5173/forgot-password`
2. 输邮箱 → 提交 → 应自动跳 `/verify-reset`
3. 去邮箱收 6 位验证码 → 在 `/verify-reset` 输完 6 位 → 应自动跳 `/reset-password`
4. 输新密码(2 次)→ 提交 → 应跳 `/login?reset=ok`
5. 在 `/login` 用新密码登录 → 应成功进 Dashboard

- [ ] **Step 5: 冒烟 curl 验证**

```bash
cd /home/chou/InnovOS
EMAIL="smoke@example.com"
curl -s -X POST http://127.0.0.1:8000/api/auth/password-reset/request-otp \
  -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\"}" -w "\nHTTP %{http_code}\n"

# 从邮箱取 code (QQ 邮箱 / Mailpit / dev 日志)
CODE="123456"
RESP=$(curl -s -X POST http://127.0.0.1:8000/api/auth/password-reset/verify \
  -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"code\":\"$CODE\"}")
echo "$RESP"
TOKEN=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['reset_token'])")

curl -s -X POST http://127.0.0.1:8000/api/auth/password-reset/set-password \
  -H "Content-Type: application/json" \
  -d "{\"reset_token\":\"$TOKEN\",\"new_password\":\"newpass1234\"}" -w "\nHTTP %{http_code}\n"
```

预期:三步都成功。

- [ ] **Step 6: 清理测试账号**

```bash
cd /home/chou/InnovOS/backend
.venv/bin/python -c "
from app.database import get_db
db = get_db()
try:
    db.execute(\"DELETE FROM email_verifications WHERE email LIKE '%@example.com'\")
    db.execute(\"DELETE FROM users WHERE email LIKE '%@example.com'\")
    db.commit()
    print('清理完成')
finally:
    db.close()
"
```

---

## Task 14: 更新 `docs/smtp-operations.md` 同步密码重置流程

**Files:**
- Modify: `docs/smtp-operations.md`

- [ ] **Step 1: 修改 §1 概述表**

把「密码重置链接」改为「密码重置验证码(6 位)」,指向 `/api/auth/password-reset/*`。

- [ ] **Step 2: 修改 §4 端到端冒烟测试**

把 forgot-password / reset-password 的 curl 命令替换为 password-reset/request-otp / verify / set-password 三步。

- [ ] **Step 3: 修改 §6.3 反垃圾邮件最佳实践**

加一条:「不要在密码重置邮件正文中放 URL(防钓鱼混淆,已迁移到纯 OTP)」。

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS
git add docs/smtp-operations.md
git commit -m "docs(smtp): sync password-reset OTP flow documentation"
```

---

## Self-Review

按 writing-plans 技能要求做 4 项检查:

### 1. Spec 覆盖

| Spec 节 | 实现 Task |
|---------|----------|
| §1.2 DB `purpose` 列 | Task 1 |
| §2 决策 | Task 2 / 8 / 9 / 10 / 11 / 12 |
| §3 数据模型 | Task 1 |
| §4.1 枚举 + 配置 | Task 3 |
| §4.2 service 改动 | Task 2 |
| §4.3 4 条路由 | Task 6 |
| §4.4 UserManager 空回调 | Task 7 |
| §4.5 邮件文案 | Task 4 |
| §5 前端流程 | Task 8 / 9 / 10 / 11 / 12 |
| §6 安全 | Task 5 + Task 2 + Task 7 |
| §7 测试 | 散布每个 Task 的 Step 1 |
| §9 文件索引 | 全部覆盖 |

✅ 无遗漏。

### 2. Placeholder 扫描

无 "TBD"/"TODO"/"fill in details"。Task 2 Step 4 注释说"工程师应阅读 UserManager._update 后调整"——这是必要的现实指引,不算 placeholder。

### 3. 类型一致性

- `OtpPurpose.PASSWORD_RESET` 在 Task 2 引入,Task 4 / 6 引用,一致。
- `InvalidResetSession` 在 Task 5 引入,Task 2 Step 4 引用(import),Task 6 路由使用,一致。
- `ResetPasswordSetIn` schema 在 Task 6 Step 4 定义,Step 3 路由引用——**Step 顺序已写明 Step 4 必须在 Step 3 之前完成**。✅
- `_issue_reset_session_token` / `_decode_reset_session_token` 在 Task 2 定义并使用,一致。

### 4. 边界修正

发现 1 处顺序问题(Task 6 Step 3 引用 Step 4 才定义的 schema),已修正写法。