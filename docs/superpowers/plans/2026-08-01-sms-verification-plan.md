# 短信验证码认证系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有邮箱 OTP 验证系统完全替换为阿里云短信验证码，手机号作为登录主标识。

**Architecture:** 保留 FastAPI Users 框架基础设施（密码哈希、JWT、用户 CRUD），深度定制 User 模型、UserManager 和认证路由。阿里云 `SendSmsVerifyCode` + `CheckSmsVerifyCode` 全权管理验证码生命周期，不自建 OTP 存储表。

**Tech Stack:** Python 3.13, FastAPI 0.115+, FastAPI Users 14+, SQLAlchemy 2.0, alibabacloud_dypnsapi20170525==2.0.0, React 19, TypeScript

## Global Constraints

- User 模型：`email` 改为 nullable（通知用），`phone` 改为 required+unique+index（登录主标识）
- 阿里云 SDK 使用 `CredentialClient()` 默认凭据链，不硬编码 AK/SK
- 开发环境无阿里云凭证时，在日志打印 `[DEV SMS] phone=xxx code=xxxx`
- 验证码校验走 `CheckSmsVerifyCode`，不本地存储 OTP
- `return_verify_code=True`（与阿里云 SDK 示例一致，但本地不依赖返回的验证码值）
- 使用赠送模板：登录/注册 100001，重置密码 100003
- 签名：`速通互联验证码`，SchemeName：`一竖光年`
- `template_param` 为 JSON 字符串格式：`{"code":"##code##","min":"5"}`（阿里云自动生成验证码）
- 双模式登录：密码登录 + 验证码登录
- 邮箱必填（仅通知），不参与验证
- 开发阶段，无真实用户，可清库重建

---

### Task 1: 添加依赖 + 配置项 + 阿里云客户端初始化

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/sms_client.py`

**Interfaces:**
- Consumes: `settings` 中的 SMS 配置项
- Produces: `SmsClient` 类（`send_code(phone, template_code)` 和 `verify_code(phone, code)` 方法）

- [ ] **Step 1: 添加 alibabacloud SDK 依赖**（版本号来自 zip 中的 `setup.py`：`>=2.0.0, <3.0.0`）

```toml
# pyproject.toml 的 dependencies 中新增
"alibabacloud_dypnsapi20170525>=2.0.0,<3.0.0",
"alibabacloud_credentials>=1.0.0",
```

- [ ] **Step 2: 在 config.py 新增 SMS 配置项**

```python
# 在 Settings 类中新增
# ── 阿里云号码认证服务 ──
SMS_SCHEME_NAME: str = "一竖光年"
SMS_SIGN_NAME: str = "速通互联验证码"
SMS_REGISTER_TEMPLATE_CODE: str = "100001"
SMS_RESET_PASSWORD_TEMPLATE_CODE: str = "100003"
SMS_CODE_LENGTH: int = 6
SMS_CODE_VALID_TIME: int = 300
SMS_RESEND_INTERVAL: int = 60
```

- [ ] **Step 3: 创建 sms_client.py**（代码直接基于 zip 中的两个 `sample.py`）

```python
"""阿里云 DYPNS 客户端封装 — 直接使用 alibabacloud_dypnsapi20170525 SDK。

参考 zip 示例代码：
- backend/app/services/sms_send_sample/alibabacloud_sample/sample.py
- backend/app/services/sms_verify_sample/alibabacloud_sample/sample.py
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsClient:
    """短信验证码客户端。开发环境无凭证时降级为日志打印。"""

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """使用凭据初始化阿里云 Client（与 zip 示例的 create_client() 一致）。"""
        try:
            from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
            from alibabacloud_credentials.client import Client as CredentialClient
            from alibabacloud_tea_openapi import models as open_api_models

            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)
            config.endpoint = "dypnsapi.aliyuncs.com"
            self._client = Dypnsapi20170525Client(config)
            logger.info("阿里云 DYPNS 客户端初始化成功")
        except Exception as e:
            logger.warning("阿里云客户端初始化失败（开发模式降级）: %s", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def send_code(self, phone: str, template_code: str) -> dict:
        """发送短信验证码（参考 sms_send_sample/sample.py）。

        Args:
            phone: 手机号
            template_code: 阿里云模板 CODE（100001 / 100003）

        Returns:
            {"success": bool, "biz_id": str | None, "message": str}
        """
        if not self._client:
            fake_code = f"{hash(phone) % 1_000_000:06d}"
            logger.info(
                "[DEV SMS] phone=%s template=%s code=%s valid=%ss",
                phone, template_code, fake_code, settings.SMS_CODE_VALID_TIME,
            )
            return {"success": True, "biz_id": "dev-mock", "message": "开发模式模拟发送"}

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # ── 参数与 sms_send_sample/sample.py 完全一致 ──
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code="86",
            phone_number=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=template_code,
            template_param=json.dumps({
                "code": "##code##",
                "min": str(settings.SMS_CODE_VALID_TIME // 60),
            }),
            code_length=settings.SMS_CODE_LENGTH,
            valid_time=settings.SMS_CODE_VALID_TIME,
            duplicate_policy=1,
            interval=settings.SMS_RESEND_INTERVAL,
            code_type=1,
            return_verify_code=True,  # 与 sample.py 一致
            auto_retry=1,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = self._client.send_sms_verify_code_with_options(request, runtime)
            body = resp.body
            if body.code == "OK":
                biz_id = body.model.biz_id if body.model else None
                logger.info("短信发送成功 phone=%s biz_id=%s", phone, biz_id)
                return {"success": True, "biz_id": biz_id, "message": "发送成功"}
            logger.error("短信发送失败 phone=%s code=%s message=%s", phone, body.code, body.message)
            return {"success": False, "biz_id": None, "message": body.message or "发送失败"}
        except Exception as error:
            # 与 sample.py 一致的错误处理模式：error.message + error.data.get("Recommend")
            error_msg = error.message if hasattr(error, "message") else str(error)
            logger.error("短信发送异常 phone=%s error=%s", phone, error_msg)
            if hasattr(error, "data") and error.data:
                logger.error("诊断地址: %s", error.data.get("Recommend"))
            return {"success": False, "biz_id": None, "message": error_msg}

    def verify_code(self, phone: str, code: str) -> bool:
        """核验短信验证码（参考 sms_verify_sample/sample.py）。

        Args:
            phone: 手机号
            code: 用户输入的验证码

        Returns:
            True 表示核验通过（PASS），False 表示核验失败
        """
        if not self._client:
            fake_code = f"{hash(phone) % 1_000_000:06d}"
            result = code == fake_code
            logger.info(
                "[DEV SMS VERIFY] phone=%s input=%s expected=%s result=%s",
                phone, code, fake_code, result,
            )
            return result

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # ── 参数与 sms_verify_sample/sample.py 完全一致 ──
        request = dypnsapi_models.CheckSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code="86",
            phone_number=phone,
            verify_code=code,
            case_auth_policy=1,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = self._client.check_sms_verify_code_with_options(request, runtime)
            body = resp.body
            if body.code == "OK" and body.model:
                passed = body.model.verify_result == "PASS"
                logger.info("验证码核验 phone=%s result=%s", phone, "PASS" if passed else "FAIL")
                return passed
            logger.error("验证码核验异常 phone=%s code=%s", phone, body.code)
            return False
        except Exception as error:
            error_msg = error.message if hasattr(error, "message") else str(error)
            logger.error("验证码核验异常 phone=%s error=%s", phone, error_msg)
            if hasattr(error, "data") and error.data:
                logger.error("诊断地址: %s", error.data.get("Recommend"))
            return False


sms_client = SmsClient()
```

- [ ] **Step 4: 安装依赖**

```bash
cd backend && uv sync
```

- [ ] **Step 5: 运行测试验证 import 正常**

```bash
cd backend && uv run python -c "from app.services.sms_client import sms_client; print('sms_client OK')"
```

---

### Task 2: User 模型变更（email nullable + phone required）

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/tests/conftest_auth.py`（seed_user、seed_admin 添加 phone）
- Modify: `backend/app/auth/seed.py`（超级用户种子添加 phone）

**Interfaces:**
- Produces: `User` 模型，`email` 可空，`phone` 必填+唯一+索引

- [ ] **Step 1: 在 config.py 新增超级用户手机号配置**

```python
# 在 Settings 类中新增
FIRST_SUPERUSER_PHONE: str = Field(
    default="", validation_alias=AliasChoices("INNOVOS_ADMIN_PHONE", "FIRST_SUPERUSER_PHONE")
)
```

- [ ] **Step 2: 修改 User 模型**

```python
# app/db/models.py
class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 覆盖 FastAPI Users 的 email 字段：改为可空，仅通知用
    email: Mapped[str | None] = mapped_column(
        String(320), nullable=True, unique=True
    )

    # 手机号：主登录标识
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )

    # 原有字段
    username = Column(String(100), nullable=True)
    role = Column(String(20), default="user")
    token_version = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

- [ ] **Step 3: 更新 conftest_auth.py 中的 seed_user 和 seed_admin**

```python
# seed_user 添加 phone
user = User(
    email="test@example.com",
    phone="13800000001",
    hashed_password=ph.hash("test1234"),
    is_active=True,
    is_superuser=False,
    is_verified=True,
    role="user",
    token_version=0,
)

# seed_admin 添加 phone
admin = User(
    email="admin@example.com",
    phone="13800000002",
    hashed_password=ph.hash("admin1234"),
    is_active=True,
    is_superuser=True,
    is_verified=True,
    role="admin",
    token_version=0,
)
```

- [ ] **Step 4: 更新 auth/seed.py 的 seed_first_superuser_if_configured**

```python
# 在创建 User 时添加 phone
user = User(
    email=email,
    phone=settings.FIRST_SUPERUSER_PHONE or "13800000000",
    hashed_password=hashed,
    is_active=True,
    is_superuser=True,
    is_verified=True,
    username=email.split("@")[0],
    role="admin",
    token_version=0,
)
```

- [ ] **Step 5: 运行测试验证模型可用**

```bash
cd backend && uv run pytest tests/test_auth_schemas.py -v
```

---

### Task 3: Auth Schemas 更新（phone 必填）

**Files:**
- Modify: `backend/app/auth/schemas.py`

- [ ] **Step 1: 修改 UserCreate 和 UserRead schema**

```python
# app/auth/schemas.py
from pydantic import Field


class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。"""
    username: str | None = None
    phone: str  # 必填
    role: str = "user"


class UserCreate(schemas.BaseUserCreate):
    """用户创建 schema。phone + password 必填，email 可选。"""
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    email: str | None = None
    username: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新 schema。"""
    username: str | None = None
    phone: str | None = None
    email: str | None = None
```

---

### Task 4: SMS 异常类 + Schemas

**Files:**
- Create: `backend/app/exceptions/sms_verification.py`
- Create: `backend/app/schemas/sms_verification.py`

- [ ] **Step 1: 创建异常类**

```python
# app/exceptions/sms_verification.py
from dataclasses import dataclass
from typing import Any
from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class SmsVerificationError(Exception):
    status: int
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def __post_init__(self):
        super().__init__(self.message)


class SmsSendFailed(SmsVerificationError):
    def __init__(self) -> None:
        super().__init__(503, "SMS_SEND_FAILED", "短信发送失败，请稍后重试")


class SmsVerifyFailed(SmsVerificationError):
    def __init__(self, remaining: int | None = None) -> None:
        detail = {"remaining": remaining} if remaining else None
        super().__init__(400, "SMS_VERIFY_FAILED", "验证码错误", detail)


class SmsRateLimited(SmsVerificationError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(429, "SMS_RATE_LIMITED", "操作过于频繁，请稍后再试", {"retry_after": retry_after})


class SmsPhoneNotFound(SmsVerificationError):
    def __init__(self) -> None:
        super().__init__(404, "PHONE_NOT_FOUND", "该手机号未注册")


async def sms_verification_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, SmsVerificationError):
        return JSONResponse(status_code=500, content={"code": "INTERNAL", "message": "服务异常"})
    body: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)
```

- [ ] **Step 2: 创建 Pydantic schemas**

```python
# app/schemas/sms_verification.py
from pydantic import BaseModel, Field


class SmsSendIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    purpose: str = "register"  # register | password_reset


class SmsVerifyIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: str = "register"


class SmsSendOut(BaseModel):
    expires_in: int = 300
    next_resend_in: int = 60


class SmsVerifyOut(BaseModel):
    verified: bool
    already: bool = False
```

---

### Task 5: Phone Verification API

**Files:**
- Create: `backend/app/api/phone_verification.py`

- [ ] **Step 1: 创建短信验证码路由**

```python
# app/api/phone_verification.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.sms_verification import (
    SmsPhoneNotFound, SmsRateLimited, SmsSendFailed, SmsVerifyFailed,
)
from app.rate_limit_redis import sms_otp_request_limiter, sms_otp_verify_limiter, sms_otp_ip_limiter
from app.schemas.sms_verification import SmsSendIn, SmsSendOut, SmsVerifyIn, SmsVerifyOut
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth/sms-verifications", tags=["auth"])


@router.post("/send", response_model=SmsSendOut, status_code=202)
def send_sms(payload: SmsSendIn, request: Request) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    template_code = (
        settings.SMS_RESET_PASSWORD_TEMPLATE_CODE
        if payload.purpose == "password_reset"
        else settings.SMS_REGISTER_TEMPLATE_CODE
    )

    result = sms_client.send_code(payload.phone, template_code)
    if not result["success"]:
        if not sms_client.available:
            raise SmsSendFailed()
        return SmsSendOut(
            expires_in=settings.SMS_CODE_VALID_TIME,
            next_resend_in=settings.SMS_RESEND_INTERVAL,
        )
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", response_model=SmsVerifyOut)
def verify_sms(payload: SmsVerifyIn, request: Request) -> SmsVerifyOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    passed = sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        return SmsVerifyOut(verified=False, already=False)

    if payload.purpose == "register":
        from app.database import db_session
        with db_session() as db:
            db.execute(
                "UPDATE users SET is_verified=TRUE, is_active=TRUE "
                "WHERE phone=%s AND is_verified=FALSE",
                (payload.phone,),
            )

    return SmsVerifyOut(verified=True, already=False)
```

---

### Task 6: 自定义注册 + 登录路由

**Files:**
- Create: `backend/app/api/auth_register.py`
- Create: `backend/app/api/auth_login.py`

- [ ] **Step 1: 创建自定义注册路由**

```python
# app/api/auth_register.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_users import exceptions as fui_exceptions
from fastapi_users.manager import BaseUserManager

from app.core.config import settings
from app.auth.schemas import UserCreate, UserRead
from app.auth.users import get_user_manager
from app.database import db_session
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: UserCreate,
    request: Request,
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    # 1. 校验手机号唯一性
    with db_session() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE phone=%s", (payload.phone,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=400,
                detail={"code": "REGISTER_PHONE_DUPLICATE", "reason": "该手机号已注册"},
            )

    # 2. 创建用户（is_verified=false, is_active=false）
    try:
        created_user = await user_manager.create(
            payload, safe=True, request=request,
        )
    except fui_exceptions.UserAlreadyExists:
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_EMAIL_DUPLICATE", "reason": "该邮箱已注册"},
        )
    except fui_exceptions.InvalidPasswordException as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "REGISTER_INVALID_PASSWORD", "reason": e.reason},
        )

    # 3. 注册后自动下发短信验证码
    sms_client.send_code(payload.phone, settings.SMS_REGISTER_TEMPLATE_CODE)

    return created_user
```

- [ ] **Step 2: 创建验证码登录路由**

```python
# app/api/auth_login.py
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth.backend import auth_backend
from app.database import db_session
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


class PhoneCodeLoginIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/login/code")
async def login_with_code(
    payload: PhoneCodeLoginIn,
    request: Request,
    response: Response,
):
    """验证码登录：核验短信验证码，成功后签发 JWT。"""
    # 1. 核验验证码
    passed = sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_CODE_INVALID", "reason": "验证码错误"},
        )

    # 2. 查找用户
    with db_session() as db:
        user_row = db.execute(
            "SELECT id, email, phone, is_active, is_superuser, is_verified "
            "FROM users WHERE phone=%s",
            (payload.phone,),
        ).fetchone()
    if not user_row:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_USER_NOT_FOUND", "reason": "该手机号未注册"},
        )

    # 3. 签发 JWT（复用 FastAPI Users 策略）
    from app.db.models import User
    user = User(
        id=user_row["id"],
        email=user_row["email"],
        phone=user_row["phone"],
        is_active=user_row["is_active"],
        is_superuser=user_row["is_superuser"],
        is_verified=user_row["is_verified"],
    )
    strategy = auth_backend.get_strategy()
    token = await strategy.write_token(user)
    await auth_backend.transport.get_login_response(token, response, request)

    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "is_verified": user.is_verified,
    }
```

---

### Task 7: 密码重置路由改为 SMS OTP

**Files:**
- Rewrite: `backend/app/api/password_reset.py`

- [ ] **Step 1: 重写 password_reset.py**

```python
# app/api/password_reset.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.exceptions.sms_verification import SmsRateLimited
from app.rate_limit_redis import sms_otp_ip_limiter, sms_otp_request_limiter, sms_otp_verify_limiter
from app.schemas.sms_verification import SmsSendOut
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth/password-reset", tags=["auth"])


class PasswordResetSendIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")


class PasswordResetVerifyIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11, pattern=r"^1\d{10}$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/send-code", response_model=SmsSendOut, status_code=202)
def send_reset_code(payload: PasswordResetSendIn, request: Request) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 防探测：不暴露手机号是否存在，静默返回
    sms_client.send_code(payload.phone, settings.SMS_RESET_PASSWORD_TEMPLATE_CODE)
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", status_code=200)
def verify_reset_code(payload: PasswordResetVerifyIn, request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 1. 核验验证码
    passed = sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "RESET_CODE_INVALID", "reason": "验证码错误"},
        )

    # 2. 查找用户 + 更新密码
    from app.auth.users import get_user_manager
    from app.auth.sync_db import SyncSQLAlchemyUserDatabase
    from app.db.models import User
    from app.db.session import _get_session_factory
    import asyncio

    factory = _get_session_factory()
    session = factory()
    try:
        user_db = SyncSQLAlchemyUserDatabase(session, User)
        manager = get_user_manager(user_db)
        user_row = session.query(User).filter(User.phone == payload.phone).one_or_none()
        if not user_row:
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "reason": "用户不存在"},
            )

        # 禁止与旧密码相同
        same_password, _ = manager.password_helper.verify_and_update(
            payload.new_password, user_row.hashed_password,
        )
        if same_password:
            raise HTTPException(
                status_code=400,
                detail={"code": "SAME_PASSWORD", "reason": "新密码不能与旧密码相同"},
            )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                manager._update(user_row, {"password": payload.new_password})
            )
        finally:
            loop.close()
    finally:
        session.close()

    return {"reset": True}
```

---

### Task 8: 限流器调整 + main.py 路由更新 + 旧文件清理

**Files:**
- Modify: `backend/app/rate_limit_redis.py`
- Modify: `backend/app/main.py`
- Delete: `backend/app/api/email_verification.py`
- Delete: `backend/app/services/email_verification_service.py`
- Delete: `backend/app/schemas/email_verification.py`
- Delete: `backend/app/exceptions/email_verification.py`

- [ ] **Step 1: 限流器改为短信版**

```python
# rate_limit_redis.py 中替换
sms_otp_request_limiter = RedisRateLimiter(max_requests=1, window_seconds=60, name="sms_otp_req")
sms_otp_verify_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="sms_otp_verify")
sms_otp_ip_limiter = RedisRateLimiter(max_requests=30, window_seconds=60, name="sms_otp_ip")
```

- [ ] **Step 2: main.py 路由注册更新**

```python
# 移除 email_verification_router 相关导入和异常处理
from app.api.phone_verification import router as sms_verification_router
from app.api.auth_register import router as custom_register_router
from app.api.auth_login import router as custom_login_router
from app.exceptions.sms_verification import (
    SmsVerificationError,
    sms_verification_exception_handler,
)

# 注册新路由
app_.include_router(sms_verification_router)
app_.include_router(custom_register_router)
app_.include_router(custom_login_router)
app_.add_exception_handler(SmsVerificationError, sms_verification_exception_handler)

# 移除旧的 email_verification 路由注册和异常处理
```

- [ ] **Step 3: 物理删除旧文件**

```bash
rm backend/app/api/email_verification.py
rm backend/app/services/email_verification_service.py
rm backend/app/schemas/email_verification.py
rm backend/app/exceptions/email_verification.py
```

---

### Task 9: 前端 API 更新

**Files:**
- Modify: `frontend/src/api/auth.ts`

- [ ] **Step 1: 更新 auth.ts**

```typescript
export const authApi = {
  // 注册：phone 必填，email 可选
  register(input: {
    phone: string;
    password: string;
    email?: string;
    username?: string;
  }): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  // 登录：手机号 + 密码（FastAPI Users 登录字段名固定为 username）
  login(phone: string, password: string): Promise<void> {
    const form = new FormData();
    form.append('username', phone);
    form.append('password', password);
    return apiRequest<void>('/api/auth/jwt/login', {
      method: 'POST',
      body: form,
    });
  },

  // 登录：手机号 + 验证码
  loginWithCode(phone: string, code: string): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/login/code', {
      method: 'POST',
      body: JSON.stringify({ phone, code }),
    });
  },

  // 发送短信验证码
  sendSmsCode(phone: string, purpose: 'register' | 'login' = 'register'):
    Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/sms-verifications/send', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose }),
    });
  },

  // 验证短信验证码
  verifySmsCode(phone: string, code: string, purpose: 'register' | 'login' = 'register'):
    Promise<{ verified: boolean; already?: boolean }> {
    return apiRequest('/api/auth/sms-verifications/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, purpose }),
    });
  },

  // 密码重置：发送验证码
  requestPasswordResetSms(phone: string):
    Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/password-reset/send-code', {
      method: 'POST',
      body: JSON.stringify({ phone }),
    });
  },

  // 密码重置：验证码 + 新密码
  resetPasswordWithSms(phone: string, code: string, newPassword: string):
    Promise<{ reset: boolean }> {
    return apiRequest('/api/auth/password-reset/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, new_password: newPassword }),
    });
  },
} as const;
```

---

### Task 10: 前端注册页面（手机号为主）

**Files:**
- Modify: `frontend/src/features/auth/RegisterPage.tsx`

- [ ] **Step 1: 重写 RegisterPage.tsx**

核心改动：
- 手机号输入置顶（必填，11 位数字校验）
- 邮箱保留（必填，仅通知用途）
- 用户名可选
- 密码输入
- 注册成功后跳转 `/verify-phone?phone=xxx`

---

### Task 11: 前端验证码页面

**Files:**
- Create: `frontend/src/features/auth/VerifyPhonePage.tsx`
- Delete: `frontend/src/features/auth/VerifyEmailPage.tsx`

- [ ] **Step 1: 创建 VerifyPhonePage.tsx**

与现有 VerifyEmailPage 几乎一致，改动：
- 文案从"已发送验证码至邮箱"改为"已发送验证码至手机"
- API 调用改为 `authApi.verifySmsCode(phone, code, 'register')`
- 重发调用改为 `authApi.sendSmsCode(phone, 'register')`
- 成功后跳转 `/login?phone=xxx`

---

### Task 12: 前端登录页面双模式

**Files:**
- Modify: `frontend/src/features/auth/LoginPage.tsx`

- [ ] **Step 1: 添加 Tab 切换**

```tsx
const [mode, setMode] = useState<'password' | 'code'>('password');

// 密码登录模式：手机号输入 + 密码输入 → authApi.login(phone, password)
// 验证码登录模式：手机号输入 → authApi.sendSmsCode(phone, 'login')
//                → 6位验证码输入 → authApi.loginWithCode(phone, code)
```

---

### Task 13: 前端路由更新

**Files:**
- Modify: `frontend/src/routes/index.tsx`

- [ ] **Step 1: 更新路由**

```tsx
// VerifyEmailPage → VerifyPhonePage
// /verify-email → /verify-phone
import { VerifyPhonePage } from '../features/auth/VerifyPhonePage';
```

---

### Task 14: 清理

- [ ] **Step 1: 删除根目录阿里云 SDK 示例 zip**

```bash
rm /home/chou/InnovOS/244d90f0-953b-43c4-ba57-c76aedc906e1-Python.zip
rm /home/chou/InnovOS/eebdda77-f136-4a46-8a58-361fc8db3bde-Python.zip
```

- [ ] **Step 2: 删除 pg_schema.py 中的 init_email_verifications 函数**

```python
# 删除 init_email_verifications 函数及其调用
```

- [ ] **Step 3: 运行全量测试**

```bash
cd backend && uv run pytest tests/ -v --tb=short
```

---

## 执行顺序依赖图

```
Task 1 (依赖 + SMS 客户端) ← 基于 zip 示例代码
  └→ Task 2 (User 模型)
       └→ Task 3 (Auth Schemas)
            └→ Task 4 (异常 + Schemas)
                 ├→ Task 5 (Phone Verification API)
                 ├→ Task 6 (注册/登录路由)
                 └→ Task 7 (密码重置)
                      └→ Task 8 (限流器 + 清理)
                           └→ Task 9+ (前端)
```

Task 1-4 可部分并行；Task 5-7 可独立开发；Task 8 需等待 5-7 完成；Task 9-13 前端工作可独立并行。