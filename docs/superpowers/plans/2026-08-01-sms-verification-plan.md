# 短信验证码认证系统 — 实施计划（基于阿里云官方 SDK 示例重写）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有邮箱 OTP 验证系统完全替换为阿里云短信验证码，手机号作为登录主标识。

**Architecture:** 保留 FastAPI Users 框架基础设施（密码哈希、JWT、用户 CRUD），深度定制 User 模型、UserManager 和认证路由。短信发送/核验完全基于压缩包内的官方 SDK 示例（`alibabacloud_sample/sample.py`），使用异步调用方式接入 FastAPI。

**Tech Stack:** Python 3.13, FastAPI 0.115+, FastAPI Users 14+, SQLAlchemy 2.0, `alibabacloud_dypnsapi20170525==2.0.0`, React 19, TypeScript

## Global Constraints

- 阿里云 SDK 依赖（来自压缩包 `requirements.txt`）：`alibabacloud_dypnsapi20170525==2.0.0`
- 客户端初始化（来自示例 `create_client()`）：`CredentialClient()` 默认凭据链 + `endpoint='dypnsapi.aliyuncs.com'`
- **使用异步方法**（来自示例 `main_async()`）：`send_sms_verify_code_with_options_async` / `check_sms_verify_code_with_options_async`，避免阻塞 FastAPI 事件循环
- 发送参数（来自示例）：`scheme_name='一竖光年'`、`country_code='86'`、`sign_name='速通互联验证码'`、`template_param='{"code":"##code##","min":"5"}'`、`code_length=6`、`valid_time=300`、`duplicate_policy=1`、`interval=60`、`code_type=1`、`return_verify_code=True`、`auto_retry=1`
- 核验参数（来自示例）：`scheme_name='一竖光年'`、`country_code='86'`、`case_auth_policy=1`
- 响应解析：发送 `resp.body.code == "OK"` + `resp.body.model.biz_id`；核验 `resp.body.code == "OK"` + `resp.body.model.verify_result == "PASS"`
- 错误处理（来自示例）：捕获异常用 `error.message` + `error.data.get("Recommend")`（诊断地址）
- 模板：登录/注册 100001，重置密码 100003
- User 模型：`email` 改 nullable（通知用），`phone` 改 required+unique+index
- 邮箱必填（仅通知），不参与验证
- 开发环境无阿里云凭证时：日志打印 `[DEV SMS] phone=xxx code=xxxx`
- 双模式登录：密码登录 + 验证码登录
- 开发阶段，无真实用户，可清库重建

---

### Task 1: 添加依赖 + 配置项 + 阿里云客户端（基于压缩包示例）

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/sms_client.py`

**Interfaces:**

- Consumes: `settings` 中的 SMS 配置项
- Produces: `SmsClient` 类（`send_code(phone, template_code) -> dict` 和 `verify_code(phone, code) -> bool`）

- [ ] **Step 1: 添加 SDK 依赖（版本与压缩包 requirements.txt 一致）**

```toml
# backend/pyproject.toml dependencies 新增
"alibabacloud_dypnsapi20170525==2.0.0",
"alibabacloud_credentials>=1.0.0",
"alibabacloud_tea_openapi>=0.3.0",
"alibabacloud_tea_util>=0.3.0",
```

- [ ] **Step 2: config.py 新增 SMS 配置**

```python
# 在 Settings 类中新增
# ── 阿里云号码认证服务（参数与官方 SDK 示例一致）──
SMS_SCHEME_NAME: str = "一竖光年"
SMS_SIGN_NAME: str = "速通互联验证码"
SMS_REGISTER_TEMPLATE_CODE: str = "100001"
SMS_RESET_PASSWORD_TEMPLATE_CODE: str = "100003"
SMS_COUNTRY_CODE: str = "86"
SMS_CODE_LENGTH: int = 6
SMS_CODE_VALID_TIME: int = 300        # 秒
SMS_CODE_VALID_MIN: int = 5           # 分钟（模板 ${min} 变量）
SMS_RESEND_INTERVAL: int = 60         # 秒
SMS_CODE_TYPE: int = 1                # 1=纯数字
SMS_DUPLICATE_POLICY: int = 1         # 1=覆盖旧验证码
SMS_AUTO_RETRY: int = 1               # 1=开启自动重试
SMS_CASE_AUTH_POLICY: int = 1         # 1=不区分大小写
SMS_ENDPOINT: str = "dypnsapi.aliyuncs.com"
```

- [ ] **Step 3: 创建 sms_client.py（基于压缩包 sample.py 改写，使用 async 方法）**

```python
"""阿里云 DYPNS 短信验证码客户端。

基于官方 SDK 示例（alibabacloud_sample/sample.py）改写：
- create_client() 与示例一致：CredentialClient 凭据链 + endpoint
- 发送/核验均使用异步方法（示例 main_async 的调用方式）
- 开发环境无凭证时降级为日志打印
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsClient:
    """短信验证码客户端。"""

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """与示例 create_client() 一致：凭据链 + 固定 endpoint。"""
        try:
            from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
            from alibabacloud_credentials.client import Client as CredentialClient
            from alibabacloud_tea_openapi import models as open_api_models

            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)
            config.endpoint = settings.SMS_ENDPOINT
            self._client = Dypnsapi20170525Client(config)
            logger.info("阿里云 DYPNS 客户端初始化成功")
        except Exception as e:
            logger.warning("阿里云客户端初始化失败（开发模式降级为日志模拟）: %s", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def _dev_code(self, phone: str) -> str:
        """开发模式伪验证码（确定性，便于调试）。"""
        return f"{abs(hash(phone)) % 1_000_000:06d}"

    async def send_code(self, phone: str, template_code: str) -> dict:
        """发送短信验证码（异步，与示例 main_async 调用方式一致）。

        Args:
            phone: 手机号
            template_code: 阿里云模板 CODE（100001 / 100003）

        Returns:
            {"success": bool, "biz_id": str | None, "message": str}
        """
        if not self._client:
            code = self._dev_code(phone)
            logger.info(
                "[DEV SMS] phone=%s template=%s code=%s valid=%ss",
                phone, template_code, code, settings.SMS_CODE_VALID_TIME,
            )
            return {"success": True, "biz_id": "dev-mock", "message": "开发模式模拟发送"}

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # 参数与官方示例完全一致（template_param 的 min 为分钟）
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code=settings.SMS_COUNTRY_CODE,
            phone_number=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=template_code,
            template_param=json.dumps({
                "code": "##code##",
                "min": str(settings.SMS_CODE_VALID_MIN),
            }),
            code_length=settings.SMS_CODE_LENGTH,
            valid_time=settings.SMS_CODE_VALID_TIME,
            duplicate_policy=settings.SMS_DUPLICATE_POLICY,
            interval=settings.SMS_RESEND_INTERVAL,
            code_type=settings.SMS_CODE_TYPE,
            return_verify_code=True,
            auto_retry=settings.SMS_AUTO_RETRY,
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 与示例 main_async 相同的异步调用
            resp = await self._client.send_sms_verify_code_with_options_async(request, runtime)
            body = resp.body
            if body.code == "OK":
                biz_id = body.model.biz_id if body.model else None
                logger.info("短信发送成功 phone=%s biz_id=%s", phone, biz_id)
                return {"success": True, "biz_id": biz_id, "message": "发送成功"}
            logger.error("短信发送失败 phone=%s code=%s message=%s", phone, body.code, body.message)
            return {"success": False, "biz_id": None, "message": body.message or "发送失败"}
        except Exception as error:
            # 与示例相同的错误处理：error.message + error.data["Recommend"]
            error_msg = getattr(error, "message", None) or str(error)
            recommend = ""
            data = getattr(error, "data", None)
            if data:
                recommend = data.get("Recommend", "")
            logger.error("短信发送异常 phone=%s error=%s recommend=%s", phone, error_msg, recommend)
            return {"success": False, "biz_id": None, "message": error_msg}

    async def verify_code(self, phone: str, code: str) -> bool:
        """核验短信验证码（异步）。

        Args:
            phone: 手机号
            code: 用户输入的验证码

        Returns:
            True 表示核验通过（VerifyResult == "PASS"）
        """
        if not self._client:
            # 开发模式：对比伪验证码
            dev_code = self._dev_code(phone)
            result = code == dev_code
            logger.info(
                "[DEV SMS VERIFY] phone=%s input=%s expected=%s result=%s",
                phone, code, dev_code, result,
            )
            return result

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # 参数与官方示例完全一致
        request = dypnsapi_models.CheckSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code=settings.SMS_COUNTRY_CODE,
            phone_number=phone,
            verify_code=code,
            case_auth_policy=settings.SMS_CASE_AUTH_POLICY,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = await self._client.check_sms_verify_code_with_options_async(request, runtime)
            body = resp.body
            if body.code == "OK" and body.model:
                passed = body.model.verify_result == "PASS"
                logger.info("验证码核验 phone=%s result=%s", phone, "PASS" if passed else "UNKNOWN")
                return passed
            logger.error("验证码核验接口异常 phone=%s code=%s", phone, body.code)
            return False
        except Exception as error:
            error_msg = getattr(error, "message", None) or str(error)
            logger.error("验证码核验异常 phone=%s error=%s", phone, error_msg)
            return False


sms_client = SmsClient()
```

- [ ] **Step 4: 安装依赖并验证**

```bash
cd backend && uv sync
cd backend && uv run python -c "from app.services.sms_client import sms_client; print('client available:', sms_client.available)"
```

- [ ] **Step 5: 单元测试（mock 阿里云响应）**

创建 `backend/tests/test_sms_client.py`：

```python
"""SmsClient 单元测试 — mock 阿里云 SDK。"""
import pytest


@pytest.fixture
def sms_client(monkeypatch):
    """构造一个 client 存在的实例，mock 阿里云 SDK 调用。"""
    from app.services.sms_client import SmsClient

    client = SmsClient()

    class FakeModel:
        biz_id = "biz-123"

    class FakeBody:
        code = "OK"
        message = "成功"
        model = FakeModel()

    class FakeResp:
        body = FakeBody()

    class FakeClient:
        async def send_sms_verify_code_with_options_async(self, req, runtime):
            return FakeResp()

    client._client = FakeClient()
    return client


class TestSendCode:
    @pytest.mark.asyncio
    async def test_send_success(self, sms_client):
        result = await sms_client.send_code("13800000000", "100001")
        assert result["success"] is True
        assert result["biz_id"] == "biz-123"


class TestVerifyCode:
    @pytest.mark.asyncio
    async def test_verify_pass(self, sms_client, monkeypatch):
        class FakeModel:
            verify_result = "PASS"

        class FakeBody:
            code = "OK"
            model = FakeModel()

        class FakeResp:
            body = FakeBody()

        async def fake_check(self, req, runtime):
            return FakeResp()

        monkeypatch.setattr(
            sms_client._client,
            "check_sms_verify_code_with_options_async",
            fake_check,
        )
        assert await sms_client.verify_code("13800000000", "123456") is True

    @pytest.mark.asyncio
    async def test_verify_unknown(self, sms_client, monkeypatch):
        class FakeModel:
            verify_result = "UNKNOWN"

        class FakeBody:
            code = "OK"
            model = FakeModel()

        class FakeResp:
            body = FakeBody()

        async def fake_check(self, req, runtime):
            return FakeResp()

        monkeypatch.setattr(
            sms_client._client,
            "check_sms_verify_code_with_options_async",
            fake_check,
        )
        assert await sms_client.verify_code("13800000000", "654321") is False
```

运行：`cd backend && uv run pytest tests/test_sms_client.py -v`，预期通过。

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/app/services/sms_client.py backend/tests/test_sms_client.py
git commit -m "feat(sms): add Alibaba Cloud SMS client based on official SDK sample"
```

---

### Task 2: User 模型变更（email nullable + phone required）

**Files:**

- Modify: `backend/app/db/models.py`
- Modify: `backend/tests/conftest_auth.py`（seed_user/seed_admin 加 phone）
- Modify: `backend/app/auth/seed.py`（首任管理员加 phone）
- Modify: `backend/app/core/config.py`（FIRST_SUPERUSER_PHONE）

**Interfaces:**

- Produces: `User` 模型，`email` 可空，`phone` 必填+唯一+索引

- [ ] **Step 1: 修改 User 模型**

```python
# backend/app/db/models.py
class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 覆盖 FastAPI Users 的 email 字段：改可空，仅通知用
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)

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

- [ ] **Step 2: 更新 conftest_auth.py 的 fixtures**

```python
# seed_user 加 phone
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

# seed_admin 加 phone
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

- [ ] **Step 3: config.py 新增 FIRST_SUPERUSER_PHONE**

```python
FIRST_SUPERUSER_PHONE: str = Field(
    default="", validation_alias=AliasChoices("INNOVOS_ADMIN_PHONE", "FIRST_SUPERUSER_PHONE")
)
```

- [ ] **Step 4: auth/seed.py 的超级用户创建加 phone**

```python
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

- [ ] **Step 5: 运行认证测试验证模型可用**

```bash
cd backend && uv run pytest tests/test_auth_register.py tests/test_auth_login.py -v
```

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(auth): make phone the primary login identifier, email nullable"
```

---

### Task 3: Auth Schemas 更新（phone 必填）

**Files:**

- Modify: `backend/app/auth/schemas.py`

- [ ] **Step 1: 修改三个 schema**

```python
# backend/app/auth/schemas.py
class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。"""
    username: str | None = None
    phone: str
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

- [ ] **Step 2: 更新 schemas 测试**

修改 `backend/tests/test_auth_schemas.py` 中所有创建用户的用例，补 `phone` 字段（11 位，`1` 开头）。

运行：`cd backend && uv run pytest tests/test_auth_schemas.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(auth): phone required in user schemas"
```

---

### Task 4: SMS 异常类 + Schemas

**Files:**

- Create: `backend/app/exceptions/sms_verification.py`
- Create: `backend/app/schemas/sms_verification.py`

- [ ] **Step 1: 创建异常类**

```python
# backend/app/exceptions/sms_verification.py
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

    def __post_init__(self) -> None:
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
        super().__init__(
            429, "SMS_RATE_LIMITED", "操作过于频繁，请稍后再试",
            {"retry_after": retry_after},
        )


class SmsPhoneNotFound(SmsVerificationError):
    def __init__(self) -> None:
        super().__init__(404, "PHONE_NOT_FOUND", "该手机号未注册")


async def sms_verification_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, SmsVerificationError):
        return JSONResponse(status_code=500, content={"code": "INTERNAL", "message": "服务异常"})
    body: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)
```

- [ ] **Step 2: 创建 Pydantic schemas**

```python
# backend/app/schemas/sms_verification.py
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

- [ ] **Step 3: Commit**

```bash
git add backend/app/exceptions/sms_verification.py backend/app/schemas/sms_verification.py
git commit -m "feat(sms): add SMS verification exceptions and schemas"
```

---

### Task 5: 短信验证码 API（发送 + 核验路由）

**Files:**

- Create: `backend/app/api/phone_verification.py`
- Test: `backend/tests/test_sms_verification_api.py`

**Interfaces:**

- Consumes: `sms_client.send_code()` / `sms_client.verify_code()`（Task 1 产出）
- Consumes: `SmsSendIn/SmsVerifyIn/SmsSendOut/SmsVerifyOut`（Task 4 产出）

- [ ] **Step 1: 创建路由**

```python
# backend/app/api/phone_verification.py
from fastapi import APIRouter, Request

from app.core.config import settings
from app.exceptions.sms_verification import SmsRateLimited
from app.rate_limit_redis import (
    sms_otp_ip_limiter,
    sms_otp_request_limiter,
    sms_otp_verify_limiter,
)
from app.schemas.sms_verification import (
    SmsSendIn, SmsSendOut, SmsVerifyIn, SmsVerifyOut,
)
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth/sms-verifications", tags=["auth"])


@router.post("/send", response_model=SmsSendOut, status_code=202)
async def send_sms(payload: SmsSendIn, request: Request) -> SmsSendOut:
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
    await sms_client.send_code(payload.phone, template_code)
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", response_model=SmsVerifyOut)
async def verify_sms(payload: SmsVerifyIn, request: Request) -> SmsVerifyOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        return SmsVerifyOut(verified=False, already=False)

    # 注册验证：翻 is_verified + is_active
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

- [ ] **Step 2: 编写 API 测试**

创建 `backend/tests/test_sms_verification_api.py`：

```python
"""短信验证码 API 测试。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.phone_verification import router
from app.exceptions.sms_verification import (
    SmsVerificationError,
    sms_verification_exception_handler,
)
from app.services import sms_client as sms_client_module
from app.services.sms_client import SmsClient


class FakeSmsClient:
    """测试用假客户端：verify 恒真，send 恒成功。"""

    async def send_code(self, phone, template_code):
        return {"success": True, "biz_id": "test-biz", "message": "ok"}

    async def verify_code(self, phone, code):
        return True


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(SmsVerificationError, sms_verification_exception_handler)
    app.dependency_overrides = {}
    return app


def test_send_code(monkeypatch):
    monkeypatch.setattr(sms_client_module, "sms_client", FakeSmsClient())
    client = TestClient(make_app())
    resp = client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 202
    assert resp.json()["expires_in"] == 300


def test_verify_success(monkeypatch):
    monkeypatch.setattr(sms_client_module, "sms_client", FakeSmsClient())
    client = TestClient(make_app())
    resp = client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "13800000000", "code": "123456"},
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is True


def test_verify_invalid_phone():
    client = TestClient(make_app())
    resp = client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "123", "code": "123456"},
    )
    assert resp.status_code == 422


def test_send_rate_limited(monkeypatch):
    monkeypatch.setattr(sms_client_module, "sms_client", FakeSmsClient())
    client = TestClient(make_app())
    # 同一手机号 60s 内第二次请求 → 429
    client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    resp = client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 429
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && uv run pytest tests/test_sms_verification_api.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/phone_verification.py backend/tests/test_sms_verification_api.py
git commit -m "feat(sms): add SMS verification send/verify endpoints"
```

---

### Task 6: 自定义注册 + 登录路由（密码 + 验证码双模式）

**Files:**

- Create: `backend/app/api/auth_register.py`
- Create: `backend/app/api/auth_login.py`
- Test: `backend/tests/test_auth_register.py`（更新）

**Interfaces:**

- Consumes: `get_user_manager`（app/auth/users.py）、`auth_backend`（app/auth/backend.py）
- Produces: `POST /api/auth/register`（phone+password）、`POST /api/auth/login/code`（phone+code）

- [ ] **Step 1: 自定义注册路由**

```python
# backend/app/api/auth_register.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_users import exceptions as fui_exceptions
from fastapi_users.manager import BaseUserManager

from app.auth.schemas import UserCreate, UserRead
from app.auth.users import get_user_manager
from app.core.config import settings
from app.database import db_session
from app.services.sms_client import sms_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: UserCreate,
    request: Request,
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    # 1. 手机号唯一性校验
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
        created_user = await user_manager.create(payload, safe=True, request=request)
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

    # 3. 自动下发短信验证码（模板 100001）
    await sms_client.send_code(payload.phone, settings.SMS_REGISTER_TEMPLATE_CODE)

    return created_user
```

- [ ] **Step 2: 自定义验证码登录路由**

```python
# backend/app/api/auth_login.py
from fastapi import APIRouter, HTTPException, Request, Response
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
    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOGIN_CODE_INVALID", "reason": "验证码错误"},
        )

    # 查找用户（含未激活的注册用户 → 自动激活）
    from app.auth.sync_db import SyncSQLAlchemyUserDatabase
    from app.auth.users import UserManager
    from app.db.models import User
    from app.db.session import _get_session_factory
    import asyncio

    factory = _get_session_factory()
    session = factory()
    try:
        user_db = SyncSQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        user = session.query(User).filter(User.phone == payload.phone).one_or_none()
        if not user:
            raise HTTPException(
                status_code=400,
                detail={"code": "LOGIN_USER_NOT_FOUND", "reason": "该手机号未注册"},
            )
        if not user.is_active or not user.is_verified:
            user.is_active = True
            user.is_verified = True
            session.commit()

        loop = asyncio.new_event_loop()
        try:
            user = loop.run_until_complete(manager.get(user.id))
            token = loop.run_until_complete(
                auth_backend.get_strategy().write_token(user)
            )
        finally:
            loop.close()
    finally:
        session.close()

    response.delete_cookie("token")
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24,
        samesite="lax",
    )
    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "is_verified": user.is_verified,
    }
```

- [ ] **Step 3: 更新注册测试**

在 `backend/tests/test_auth_register.py` 中：

- `test_register_success`：改为传 `phone` 必填，断言返回的 `phone`
- 新增 `test_register_duplicate_phone`：同一手机号二次注册 → 400
- `test_register_phone_optional` → 删除（phone 现在必填）
- 新增 `test_register_invalid_phone`：非法手机号 → 422

- [ ] **Step 4: 运行测试**

```bash
cd backend && uv run pytest tests/test_auth_register.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/auth_register.py backend/app/api/auth_login.py backend/tests/test_auth_register.py
git commit -m "feat(auth): phone-based register and SMS code login"
```

---

### Task 7: 密码重置路由改为短信 OTP

**Files:**

- Modify: `backend/app/api/password_reset.py`
- Test: `backend/tests/test_auth_reset_password.py`（更新）

- [ ] **Step 1: 重写 password_reset.py**

```python
# backend/app/api/password_reset.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.exceptions.sms_verification import SmsRateLimited
from app.rate_limit_redis import (
    sms_otp_ip_limiter,
    sms_otp_request_limiter,
    sms_otp_verify_limiter,
)
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
async def send_reset_code(payload: PasswordResetSendIn, request: Request) -> SmsSendOut:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_request_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 防探测：不暴露手机号是否存在
    await sms_client.send_code(payload.phone, settings.SMS_RESET_PASSWORD_TEMPLATE_CODE)
    return SmsSendOut(
        expires_in=settings.SMS_CODE_VALID_TIME,
        next_resend_in=settings.SMS_RESEND_INTERVAL,
    )


@router.post("/verify", status_code=200)
async def verify_reset_code(
    payload: PasswordResetVerifyIn, request: Request
) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not sms_otp_ip_limiter.check(ip)[0]:
        raise SmsRateLimited(60)
    if not sms_otp_verify_limiter.check(payload.phone)[0]:
        raise SmsRateLimited(60)

    # 1. 核验验证码
    passed = await sms_client.verify_code(payload.phone, payload.code)
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"code": "RESET_CODE_INVALID", "reason": "验证码错误"},
        )

    # 2. 更新密码（复用 UserManager 的 bcrypt 哈希逻辑）
    from app.auth.sync_db import SyncSQLAlchemyUserDatabase
    from app.auth.users import UserManager
    from app.db.models import User
    from app.db.session import _get_session_factory
    import asyncio

    factory = _get_session_factory()
    session = factory()
    try:
        user_db = SyncSQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        user = session.query(User).filter(User.phone == payload.phone).one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "reason": "用户不存在"},
            )
        same_password, _ = manager.password_helper.verify_and_update(
            payload.new_password, user.hashed_password,
        )
        if same_password:
            raise HTTPException(
                status_code=400,
                detail={"code": "SAME_PASSWORD", "reason": "新密码不能与旧密码相同"},
            )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                manager._update(user, {"password": payload.new_password})
            )
        finally:
            loop.close()
    finally:
        session.close()

    return {"reset": True}
```

- [ ] **Step 2: 更新测试**

修改 `backend/tests/test_auth_reset_password.py`：email 字段全部替换为 phone（11 位）。

- [ ] **Step 3: 运行测试**

```bash
cd backend && uv run pytest tests/test_auth_reset_password.py -v
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(auth): password reset via SMS OTP"
```

---

### Task 8: 限流器调整 + 旧邮箱路由清理

**Files:**

- Modify: `backend/app/rate_limit_redis.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/tables/pg_schema.py`
- Modify: `backend/app/auth/users.py`（on_after_register 改为发短信）
- Delete: `backend/app/api/email_verification.py`
- Delete: `backend/app/services/email_verification_service.py`
- Delete: `backend/app/schemas/email_verification.py`
- Delete: `backend/app/exceptions/email_verification.py`

- [ ] **Step 1: 限流器改为短信版**

```python
# backend/app/rate_limit_redis.py 替换 email_otp_* 三个实例
sms_otp_request_limiter = RedisRateLimiter(max_requests=1, window_seconds=60, name="sms_otp_req")
sms_otp_verify_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="sms_otp_verify")
sms_otp_ip_limiter = RedisRateLimiter(max_requests=30, window_seconds=60, name="sms_otp_ip")
```

- [ ] **Step 2: main.py 路由更新**

```python
# 删除:
# from app.api.email_verification import router as email_verification_router
# from app.exceptions.email_verification import (EmailVerificationError, email_verification_exception_handler)

# 新增:
from app.api.phone_verification import router as sms_verification_router
from app.exceptions.sms_verification import SmsVerificationError, sms_verification_exception_handler

app_.include_router(sms_verification_router)
app_.add_exception_handler(SmsVerificationError, sms_verification_exception_handler)
```

- [ ] **Step 3: pg_schema.py 移除 init_email_verifications**

删除 `init_email_verifications` 函数及调用处（如果有）。

- [ ] **Step 4: auth/users.py 的 on_after_register 改为发短信**

```python
async def on_after_register(self, user, request=None):
    log_audit(...)
    # 注册后自动下发短信验证码（失败不阻塞注册响应）
    try:
        from app.services.sms_client import sms_client
        await sms_client.send_code(user.phone, settings.SMS_REGISTER_TEMPLATE_CODE)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("短信下发失败: %s", e)
```

- [ ] **Step 5: 物理删除旧文件**

```bash
rm backend/app/api/email_verification.py
rm backend/app/services/email_verification_service.py
rm backend/app/schemas/email_verification.py
rm backend/app/exceptions/email_verification.py
rm backend/app/tables/pg_schema.py 中 email_verifications 相关代码
```

- [ ] **Step 6: 检查残留引用**

```bash
grep -rn "email_verification" backend/app/ --include="*.py"
# 若有残留，逐一清理
```

- [ ] **Step 7: 运行全量后端测试**

```bash
cd backend && uv run pytest tests/ -v
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(auth): remove email OTP, wire SMS verification into pipeline"
```

---

### Task 9: 前端 API 更新（phone 化）

**Files:**

- Modify: `frontend/src/api/auth.ts`

- [ ] **Step 1: 更新 auth.ts**

```typescript
// 替换 email OTP 端点为短信端点
export const authApi = {
  /** 注册：phone 必填，email 可选（通知用） */
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

  /** 登录：手机号 + 密码 */
  login(phone: string, password: string): Promise<void> {
    const form = new FormData();
    form.append('username', phone);
    form.append('password', password);
    return apiRequest<void>('/api/auth/jwt/login', {
      method: 'POST',
      body: form,
    });
  },

  /** 登录：手机号 + 验证码 */
  loginWithCode(phone: string, code: string): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/login/code', {
      method: 'POST',
      body: JSON.stringify({ phone, code }),
    });
  },

  /** 发送短信验证码（注册/登录） */
  sendSmsCode(
    phone: string,
    purpose: 'register' | 'login' = 'register',
  ): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/sms-verifications/send', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose }),
    });
  },

  /** 核验短信验证码（注册场景：通过后激活账号） */
  verifySmsCode(
    phone: string,
    code: string,
    purpose: 'register' | 'login' = 'register',
  ): Promise<{ verified: boolean; already?: boolean }> {
    return apiRequest('/api/auth/sms-verifications/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, purpose }),
    });
  },

  /** 密码重置：发送短信验证码 */
  requestPasswordResetSms(phone: string): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/password-reset/send-code', {
      method: 'POST',
      body: JSON.stringify({ phone }),
    });
  },

  /** 密码重置：验证码 + 新密码 */
  resetPasswordWithSms(
    phone: string,
    code: string,
    newPassword: string,
  ): Promise<{ reset: boolean }> {
    return apiRequest('/api/auth/password-reset/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, new_password: newPassword }),
    });
  },
};
```

- [ ] **Step 2: 移除已废弃的 email OTP 方法**（`requestEmailOtp`/`resendEmailOtp`/`verifyEmailOtp`）

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/auth.ts
git commit -m "feat(auth): switch frontend API to SMS verification"
```

---

### Task 10: 前端注册页（phone 为主）

**Files:**

- Modify: `frontend/src/features/auth/RegisterPage.tsx`

- [ ] **Step 1: 重写 RegisterPage.tsx**

核心改动（保持现有 UI 风格 dark slate）：

1. 字段顺序：手机号（必填，11 位）→ 邮箱（必填，通知用）→ 用户名（可选）→ 密码 → 确认密码
2. 手机号校验：`/^1\d{10}$/`
3. 注册成功后跳转 `/verify-phone?phone=${phone}`（不再 `/verify-email?email=...`）
4. 手机号输入加图标（`Phone`），邮箱加 `Mail`

- [ ] **Step 2: 更新 RegisterPage 测试**

修改 `frontend/src/features/auth/__tests__/RegisterPage.test.tsx`：

- 注册表单提交数据从 `{email, password, phone?}` 改为 `{phone, email, password}`
- 跳转断言从 `/verify-email` 改为 `/verify-phone`

- [ ] **Step 3: 测试 + Commit**

```bash
cd frontend && npm test -- RegisterPage
git commit -am "feat(auth): phone-first registration page"
```

---

### Task 11: 前端验证码页面（VerifyPhonePage）

**Files:**

- Create: `frontend/src/features/auth/VerifyPhonePage.tsx`
- Delete: `frontend/src/features/auth/VerifyEmailPage.tsx`
- Test: `frontend/src/features/auth/__tests__/VerifyPhonePage.test.tsx`

- [ ] **Step 1: 创建 VerifyPhonePage.tsx**

基于现有 VerifyEmailPage.tsx 复制，改动：

1. 文案：「验证手机号」标题；`已发送验证码至手机 {phone}`
2. API 调用：`authApi.verifySmsCode(phone, code, 'register')` 替代 `verifyEmailOtp`
3. 重发：`authApi.sendSmsCode(phone, 'register')` 替代 `resendEmailOtp`
4. 成功跳转：`/login?phone=${phone}`
5. 图标从 `Mail` 改为 `Smartphone`

- [ ] **Step 2: 删除 VerifyEmailPage.tsx 及测试**

```bash
rm frontend/src/features/auth/VerifyEmailPage.tsx
rm frontend/src/features/auth/__tests__/VerifyEmailPage.test.tsx
rm frontend/src/features/auth/__tests__/LoginPageVerifyRedirect.test.tsx  # 若引用 verify-email 路由
```

- [ ] **Step 3: 更新路由 index.tsx**

```tsx
// /verify-email → /verify-phone
import { VerifyPhonePage } from '../features/auth/VerifyPhonePage';
// 路由: { path: '/verify-phone', element: <VerifyPhonePage /> }
```

- [ ] **Step 4: 测试 + Commit**

```bash
cd frontend && npm test
git commit -am "feat(auth): replace verify-email page with verify-phone"
```

---

### Task 12: 前端登录页双模式

**Files:**

- Modify: `frontend/src/features/auth/LoginPage.tsx`

- [ ] **Step 1: 添加 Tab 切换（密码 / 验证码）**

```tsx
const [mode, setMode] = useState<'password' | 'code'>('password');

// Tab 切换 UI（保持现有 dark slate 风格）：
// 「密码登录」|「验证码登录」

// 密码模式：phone + password → authApi.login(phone, password)
// 验证码模式：phone → authApi.sendSmsCode(phone, 'login')（带 60s 倒计时重发）
//   → 6 位验证码输入 → authApi.loginWithCode(phone, code)
```

- [ ] **Step 2: 更新登录测试**

修改 `frontend/src/features/auth/__tests__/LoginPageVerifyRedirect.test.tsx`（若保留），
新增验证码登录模式用例。

- [ ] **Step 3: 测试 + Commit**

```bash
cd frontend && npm test -- LoginPage
git commit -am "feat(auth): dual-mode login page (password + SMS code)"
```

---

### Task 13: 数据库迁移 + 清理根目录 zip

**Files:**

- Execute: SQL 迁移（开发阶段直接清库）

- [ ] **Step 1: 数据库变更**

开发阶段无真实用户，直接重建：

```sql
TRUNCATE users CASCADE;
DROP TABLE IF EXISTS email_verifications;
-- users 表结构由 SQLAlchemy 自动重建（email nullable + phone unique）
```

- [ ] **Step 2: 删除根目录 zip**

```bash
rm /home/chou/InnovOS/244d90f0-953b-43c4-ba57-c76aedc906e1-Python.zip
rm /home/chou/InnovOS/eebdda77-f136-4a46-8a58-361fc8db3bde-Python.zip
```

- [ ] **Step 3: 全量回归（前后端）**

```bash
make test
```

- [ ] **Step 4: 手动端到端验证（开发模式）**

```bash
make dev
# 1. 打开 http://localhost:5173/register
# 2. 手机号 + 邮箱 + 密码注册 → 跳转 /verify-phone
# 3. 查看后端日志 [DEV SMS] phone=... code=...
# 4. 输入日志中的验证码 → 验证成功 → 跳转登录
# 5. 手机号 + 密码登录 → 成功
# 6. 手机号 + 验证码登录 → 成功
# 7. 忘记密码 → 发短信 → 验证码 + 新密码 → 修改成功
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: database migration for SMS verification"
```

---

## 执行顺序依赖图

```
Task 1 (SDK 依赖 + SmsClient)  ← 基于压缩包 sample.py
  ├→ Task 2 (User 模型 phone 主键)
  │    └→ Task 3 (Auth Schemas)
  ├→ Task 4 (异常 + Schemas) ──┐
  │                            ├→ Task 5 (SMS API 路由)
  ├→ Task 6 (注册/登录路由)     ├→ Task 7 (密码重置)
  │                            └→ Task 8 (限流器 + 清理旧邮箱 OTP)
  └→ Task 9-12 (前端，可与后端并行)
       └→ Task 13 (数据库迁移 + 收尾)
```

Task 1-3 顺序执行；Task 4-7 可在 Task 1 完成后并行；Task 8 需等 5-7；前端 9-12 可从 Task 5 之后并行启动。
