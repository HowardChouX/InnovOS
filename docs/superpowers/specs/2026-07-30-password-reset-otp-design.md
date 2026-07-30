# InnovOS 密码重置：验证码（OTP）链路

- **日期**: 2026-07-30
- **状态**: 已确认，待落计划
- **作者**: HowardChouX
- **关联**: InnovOS `dev2` 分支；前序 spec `2026-07-29-email-verification-design.md`、`2026-07-28-auth-fastapi-users-design.md`
- **本次需求**: 重置密码不再依赖邮件中的 URL token,改为向用户邮箱发送 6 位 OTP,前端通过 React Router `location.state` 把验证状态传到下一页面。

## 1. 目标与范围

### 1.1 顶层目标

把 InnovOS 的密码重置流程从「邮件链接 + JWT token」改为「6 位邮件 OTP + 短期 reset_session token」,与 InnovOS 已有的邮箱验证 OTP 体系保持一致形态,降低用户使用门槛(尤其移动端无法方便点击邮件链接时)。

### 1.2 范围

- DB:`email_verifications` 表加 `purpose` 列(纯 DDL,无数据回填)。
- 后端:`EmailVerificationService` 全部方法加 `purpose` 参数;新增 4 条密码重置路由;复用 OTP 限流。
- 前端:3 页分离(`/forgot-password` → `/verify-reset` → `/reset-password`);`ResetPasswordPage` 重写;新增 `VerifyResetOtpPage`;`ForgotPasswordPage` 调整跳转目标。
- 邮件:密码重置邮件只发 6 位验证码,不再发 URL 链接。
- 安全:复用现有 OTP 哈希与节流策略;新增 `reset_session` JWT secret + 10 分钟过期。
- 文档:`docs/smtp-operations.md` 同步更新密码重置流程章节。

### 1.3 不在范围内

- 手机号短信重置。
- 安全问题(忘记密码)的多因子二次认证。
- 修改现有 `email_verification` 的 OTP 流程(邮箱验证仍走 `purpose=email_verification`)。
- 移除 fastapi-users 内置的 `get_reset_password_router()`(保留向后兼容,调用方在 InnovOS 流程下不再触发)。

## 2. 已确认的架构决策

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 验证码类型 | 复用现有 6 位邮件 OTP | 用户体验与邮箱验证一致;移动端友好 |
| 数据存储 | `email_verifications` 表加 `purpose` 列 | 避免双表逻辑重复;支持未来更多用途 |
| 邮件内容 | 只发 6 位验证码(去 URL) | 用户选择;简化文案,降低误点击风险 |
| 验证码隔离 | 重置必须用 `purpose=password_reset`,与邮箱验证不通 | 安全要求;防止跨场景滥用 |
| 后端调用 | 两步走(verify → set-password) | 中途取消不浪费验证码;审计粒度更细 |
| 状态传递 | React Router `location.state`(email + reset_token) | 不写 URL;刷新丢失可恢复 |
| 限流 | 复用现有 OTP 限流 | 减少配置面;验证后行为相同 |
| reset_token 有效期 | 10 分钟 | 与 OTP TTL 对齐 |
| reset_token 签名 | 独立 JWT secret + audience `password-reset:consume` | 不复用登录 JWT secret;防越权 |

## 3. 数据模型

### 3.1 `email_verifications` 表 — 加 `purpose` 列

- 位置:Alembic migration(`alembic/versions/<rev>_add_purpose_to_email_verifications.py`)。
- 变更:

```sql
-- 幂等 DDL;Alembic 用 IF NOT EXISTS 等价表达
ALTER TABLE email_verifications
ADD COLUMN IF NOT EXISTS purpose VARCHAR(32) NOT NULL DEFAULT 'email_verification';

CREATE INDEX IF NOT EXISTS email_verifications_email_purpose_idx
ON email_verifications(email, purpose);
```

- 字段语义:

| 取值 | 含义 | 触发场景 |
| --- | --- | --- |
| `email_verification` | 邮箱验证(默认值) | 用户注册 / 重发 |
| `password_reset` | 密码重置 | 用户忘记密码 / 重发 |

- 迁移策略:纯 schema 声明,**无数据回填**(老行自动落到 `email_verification`,与原行为等价)。符合 CLAUDE.md "One-shot Migration Code" 要求。
- 索引作用:支持 `(email, purpose, consumed_at, expires_at)` 高效联合查询。

## 4. 后端

### 4.1 枚举与配置(`backend/app/services/email_verification_service.py`)

```python
class OtpPurpose(str, Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
```

新增 settings 字段(`backend/app/core/config.py`):

```python
RESET_SESSION_TOKEN_TTL_SECONDS: int = 600  # 10 分钟
RESET_SESSION_JWT_SECRET: str = Field(
    default_factory=lambda: settings.SECRET_KEY,  # 默认复用,但允许独立配置
)
RESET_SESSION_JWT_AUDIENCE: str = "password-reset:consume"
```

### 4.2 `EmailVerificationService` 改动

| 方法 | 改动 |
| --- | --- |
| `issue_for_user(user, request, purpose=OtpPurpose.EMAIL_VERIFICATION)` | 写入新行的 `purpose` 字段 |
| `resend(email, request, purpose=OtpPurpose.EMAIL_VERIFICATION)` | 查询/插入都按 `(email, purpose)` 隔离 |
| `verify(email, code, purpose=OtpPurpose.EMAIL_VERIFICATION)` | 按 `(email, purpose)` 查询;**`PASSWORD_RESET` 分支额外签发 `reset_session_token`** 并返回 |
| `consume_reset_session(token) -> user_id` (新增) | 解码 JWT → 校验 audience = `password-reset:consume` + 未过期 → 返回 user_id |
| `set_password_with_session(token, new_password) -> user` (新增) | 调 `consume_reset_session` → `UserManager.validate_password` → 写 `users.hashed_password` → 返回 user;同一事务消费 token |

**关键不变量:**
- 重置密码成功后:①当前验证用的 OTP 记录 `consumed_at = NOW()`;②同 `(email, purpose='password_reset')` 的其他未消费活跃 OTP 一并 `consumed_at = NOW()`(防重放)。
- `reset_session_token` 一次性消费:成功改密后在 `reset_session_tokens` 表新增一行标记 `consumed_at`;再次使用抛 `InvalidResetSession`。
- `EMAIL_VERIFICATION` 分支保持现状不变(不签发 reset_token)。

### 4.3 路由(`backend/app/api/email_verification.py`)

**现有端点(保持):**

```python
POST /api/auth/email-verifications/request      {email} → 202
POST /api/auth/email-verifications/resend       {email} → 202
POST /api/auth/email-verifications/verify       {email, code, purpose?} → 200
                                            # purpose 默认 email_verification
                                            # password_reset 时返回 reset_token
```

**新增端点:**

```python
POST /api/auth/password-reset/request-otp       {email} → 202 (防探测,与现有 request 同语义,purpose=password_reset)
POST /api/auth/password-reset/resend-otp        {email} → 202 (purpose=password_reset 重发)
POST /api/auth/password-reset/verify            {email, code} → {verified:true, reset_token:"..."}
POST /api/auth/password-reset/set-password      {reset_token, new_password} → 200
```

**为什么独立路径而不是复用 `email-verifications/*`?**
- URL 语义清晰:路径直接表达流程意图,便于日志/监控分流
- 异常类型不重叠:`AlreadyVerified` 不应出现在重置场景
- 保留未来按路径调独立限流策略的灵活性

### 4.4 `UserManager.on_after_forgot_password` 回调处理

`backend/app/auth/users.py:45-50` 现有回调(由 fastapi-users 默认 reset router 触发)改为 **不发送邮件**。InnovOS 走自研 OTP 流程,fastapi-users 的内置 reset router 调用方在 InnovOS 流程下应被禁用:

```python
async def on_after_forgot_password(self, user, token, request=None):
    # InnovOS 流程不依赖此回调(走 /api/auth/password-reset/request-otp)。
    # 保留方法仅为了满足 fastapi-users 接口约束,实际为空操作。
    pass
```

fastapi-users 的 `get_reset_password_router()` 仍保留挂载(`main.py:245-248`),但 InnovOS 前端不再调用其两个端点。如未来需要切回默认流程,可恢复原实现。

### 4.5 邮件文案(`backend/app/services/email_service.py`)

- 复用现有 `_wrap_card` / `_brand_logo` / `_code_pill` / `_footer_note` helper。
- `send_password_reset_otp_sync(user, code, ttl_seconds)` 新增:正文只发 6 位验证码 + 「10 分钟内有效」+ 「如果不是您本人操作…」。
- **删除** `send_reset_password_email_sync`(URL 链接版)的所有调用方;函数本身保留(deprecation 注释)。

## 5. 前端

### 5.1 路由(`frontend/src/routes/index.tsx`)

```tsx
{ path: '/forgot-password', element: <ForgotPasswordPage /> },   // 现状保留
{ path: '/verify-reset', element: <VerifyResetOtpPage /> },      // 新增
{ path: '/reset-password', element: <ResetPasswordPage /> },     // 重写
```

### 5.2 第 1 页 — `/forgot-password`

- 行为与现状一致:输邮箱 → 调 `authApi.requestPasswordResetOtp(email)` → 显示「已发送」+ 60s 重发倒计时
- 防探测:无论邮箱是否存在都返回成功提示
- 文案微调:把「如果您收到重置链接…」改为「验证码会发送到您的邮箱」

### 5.3 第 2 页 — `/verify-reset`(新增 `VerifyResetOtpPage.tsx`)

- 从 `location.state.email` 取邮箱(直接访问跳 `/forgot-password`)
- 6 位 OTP 输入框(风格复用 `VerifyEmailPage.tsx`,抽 `OtpInput` 组件可选)
- 提交 → `authApi.verifyPasswordResetOtp(email, code)`
- 成功后:

```ts
navigate('/reset-password', {
  state: { email, reset_token },
  replace: true,  // 阻止用户点「后退」回到此页重提交
});
```

- 失败:显示错误信息 + 重置输入框

### 5.4 第 3 页 — `/reset-password`(重写)

- 从 `location.state` 取 `email` + `reset_token`,缺失则跳 `/forgot-password`
- 两个密码输入框 + 「重置密码」按钮(沿用现状 UI)
- 提交 → `authApi.setNewPassword(reset_token, new_password)`
- 成功 → `navigate('/login?reset=ok')`
- 失败:401(token 过期/被消费)→ 提示「会话已过期,请重新获取验证码」+ 跳 `/forgot-password`

### 5.5 API 客户端(`frontend/src/api/auth.ts`)

新增 3 个方法:

```ts
requestPasswordResetOtp(email: string): Promise<void>
verifyPasswordResetOtp(email: string, code: string): Promise<{reset_token: string}>
setNewPassword(reset_token: string, new_password: string): Promise<void>
```

旧 `forgotPassword` / `resetPassword` 方法保留(deprecation 注释),待 fastapi-users 默认 router 完全移除后再删。

### 5.6 Zustand store 影响

`useAuthStore` 不需要改动(密码重置流程不涉及登录态)。

## 6. 安全

| 项 | 措施 |
| --- | --- |
| OTP 哈希 | 沿用 `OTP_PEPPER + SHA-256(code)`;`RESET_SESSION_JWT_SECRET` 独立配置,不与登录 JWT secret 共享 |
| reset_token | audience=`password-reset:consume`;TTL=10 分钟;一次性消费(入库 `consumed_at` 防重放) |
| 验证码跨场景隔离 | 重置必须用 `purpose=password_reset`;邮箱验证必须用 `purpose=email_verification`;DB 查询硬约束 |
| 防探测 | `request-otp` 永远 202;查 email 存在时仍返回成功 |
| 错误次数 | `email_verifications.attempts` 上限 5,超限置 `consumed_at`(与现状一致) |
| HTTPS / Cookie | 沿用现有 `cookie_secure=True` / `__Host-` 前缀 |
| 日志 | reset_token / new_password 不进 INFO 日志;仅错误码(`EMAIL_NOT_FOUND` 等)记审计 |

## 7. 测试

### 7.1 后端(`backend/tests/test_password_reset_otp.py` 新文件)

| 测试 | 覆盖点 |
| --- | --- |
| `test_request_otp_creates_password_reset_purpose_row` | 下发后 DB 行 `purpose='password_reset'` |
| `test_email_verification_otp_cannot_reset_password` | 用 `purpose=email_verification` 的 OTP 调重置 verify → 401 |
| `test_password_reset_otp_cannot_verify_email` | 用 `purpose=password_reset` 的 OTP 调邮箱 verify → 401 |
| `test_verify_returns_reset_token_for_password_reset_purpose` | 重置 verify 返回 `{reset_token}` |
| `test_set_password_with_expired_reset_token_returns_401` | 过期 token → 401 |
| `test_set_password_with_consumed_reset_token_returns_401` | 二次使用 → 401 |
| `test_set_password_wrong_audience_returns_401` | 错误 audience → 401 |
| `test_full_flow_request_verify_set` | 端到端闭环 |

### 7.2 前端(`frontend/src/features/auth/__tests__/`)

- `VerifyResetOtpPage.test.tsx`:邮箱缺失跳回 /forgot-password;6 位验证码自动提交;成功后跳 /reset-password 带 state
- `ResetPasswordPage.test.tsx`(重写):state 缺失跳回 /forgot-password;提交按钮在 loading 时禁用;401 → 跳 /forgot-password

### 7.3 端到端冒烟

```bash
# 1. 请求 OTP
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/request-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@example.com"}'

# 2. 从邮箱取 OTP,调 verify,取 reset_token
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/verify \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@example.com","code":"199622"}'

# 3. 用 reset_token 改密码
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/set-password \
  -H "Content-Type: application/json" \
  -d '{"reset_token":"...","new_password":"newpass1234"}'
```

## 8. 迁移与回滚

### 8.1 上线步骤

1. 部署后端:触发 Alembic 迁移(自动)→ `email_verifications.purpose` 列与索引到位
2. 部署前端:3 页路由生效
3. 监控 24 小时:`POST /api/auth/password-reset/*` 流量、`email_verifications.purpose='password_reset'` 行数

### 8.2 回滚方案

- 后端 Alembic down revision:删 `email_verifications_email_purpose_idx` + `purpose` 列
- 前端回退到上一版本
- 数据无破坏:`purpose='email_verification'` 老行原样保留

### 8.3 兼容性

- 老用户未迁移行为:无(老用户没在重置密码中)
- 老客户端:无外部客户端
- `fastapi_users.get_reset_password_router()` 保留挂载(空操作回调);InnovOS 前端不再调用

## 9. 相关文件索引

| 文件 | 改动 |
| --- | --- |
| `backend/app/tables/pg_schema.py` | 加 `email_verifications.purpose` 列(同步) |
| `backend/alembic/versions/<rev>_add_purpose_to_email_verifications.py` | 新增 Alembic migration |
| `backend/app/core/config.py` | 加 `RESET_SESSION_*` 配置 |
| `backend/app/services/email_verification_service.py` | 加 `OtpPurpose` 枚举 + `consume_reset_session` / `set_password_with_session` |
| `backend/app/api/email_verification.py` | 加 `purpose` 参数 + 新增 4 条密码重置路由 |
| `backend/app/api/password_reset.py`(新) | 新建密码重置路由文件 |
| `backend/app/auth/users.py` | `on_after_forgot_password` 改空操作 |
| `backend/app/services/email_service.py` | 加 `send_password_reset_otp_sync`;deprecate `send_reset_password_email_sync` 调用 |
| `backend/tests/test_password_reset_otp.py`(新) | 8 个测试 |
| `frontend/src/api/auth.ts` | 加 3 个方法;deprecate 旧的 `forgotPassword` / `resetPassword` |
| `frontend/src/routes/index.tsx` | 加 `/verify-reset` 路由 |
| `frontend/src/features/auth/ForgotPasswordPage.tsx` | 文案微调 + 调新 endpoint |
| `frontend/src/features/auth/VerifyResetOtpPage.tsx`(新) | 6 位 OTP 输入页 |
| `frontend/src/features/auth/ResetPasswordPage.tsx` | 重写:state 缺失跳回 / 改新 endpoint |
| `frontend/src/features/auth/__tests__/VerifyResetOtpPage.test.tsx`(新) | |
| `frontend/src/features/auth/__tests__/ResetPasswordPage.test.tsx`(重写) | |
| `docs/smtp-operations.md` | 同步更新密码重置流程章节 |