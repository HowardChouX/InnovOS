# InnovOS 邮箱验证：6 位邮件 OTP 强制链路

- **日期**: 2026-07-29
- **状态**: 已确认，待落计划
- **作者**: HowardChouX
- **关联**: InnovOS `dev2` 分支；前序 spec `2026-07-28-auth-fastapi-users-design.md`

## 1. 目标与范围

### 1.1 顶层目标

注册必须经过邮箱验证。系统以 6 位邮件验证码（OTP）完成验证，未验证账号禁止登录。沿用 FastAPI Users 的登录 / 重置密码体系，但绕开其原生 verification router，改用自建 OTP 通道。

### 1.2 范围

- 后端：新增 `email_verifications` 表、`email_verification_service`、三条 OTP 路由；`UserManager.on_after_register` 自动发码；`get_auth_router(..., requires_verification=True)`。
- 前端：注册页改为注册成功跳 `/verify-email`；新增 `VerifyEmailPage`；`LoginPage` 401 拦截跳验证页；`useAuthStore.register` 不再自动 `login`。
- 配置：新增 `INNOVOS_OTP_PEPPER / OTP_TTL_SECONDS / OTP_MAX_ATTEMPTS / OTP_RESEND_COOLDOWN / EMAIL_OTP_SOFT_FAIL`。
- 邮件：dev 默认走 Mailpit，未配 SMTP 时 OTP 明文写 INFO 日志（仅 development）。
- 文档：`docs/architecture.md` / `docs/development.md` / `.env.example` 同步更新。

### 1.3 不在范围内

- 手机号短信验证、图形 / 行为验证码。
- reset password 流程调整（保留现有实现）。
- 引入新的第三方依赖。
- 改 `requires_verification` 之外的 fastapi-users 默认行为。

## 2. 已确认的架构决策

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 验证形式 | 6 位数字邮件 OTP | 用户体验直观、与 UI 输入框强一致 |
| 存储 | PostgreSQL 新表 `email_verifications` | 持久化、可查证、可清退；与现有 `pg_schema.py` 风格一致 |
| 重发 / 错误策略 | 严控：重发作废旧码、5 次错误即作废 | 抗重放、抗爆破 |
| Dev 邮件源 | Mailpit（`profile=mail`） + 未配 SMTP 时 INFO 日志输出 | 本地不依赖外部 SMTP 即可联调 |
| 验证后路径 | 跳 `/login?email=...` 手动登录 | 与 `requires_verification=True` 配合；不破坏 fastapi-users 既有登录路径 |

## 3. 数据模型

### 3.1 `email_verifications` 表

- 位置：`backend/app/tables/pg_schema.py`，以 `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` 形式追加。
- 字段：

| 字段 | 类型 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | PK | 主键 |
| `user_id` | `INTEGER` | NOT NULL, FK `users(id) ON DELETE CASCADE`, INDEX | 关联用户 |
| `email` | `VARCHAR(255)` | NOT NULL, INDEX | 冗余邮箱，便于按邮箱重发 / 清理 |
| `code_hash` | `CHAR(64)` | NOT NULL | SHA-256(code + PEPPER) hex；不存明文 |
| `attempts` | `SMALLINT` | NOT NULL DEFAULT 0 | 错误尝试次数 |
| `max_attempts` | `SMALLINT` | NOT NULL DEFAULT 5 | 上限（写死） |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | 创建时间 + 10 分钟 |
| `consumed_at` | `TIMESTAMPTZ` | NULL | 验证通过或耗尽 / 过期后置位 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | 创建时间 |
| `last_sent_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | 重发节流 |

- 索引：
  - `email_verifications_user_id_idx` ON `(user_id)`
  - `email_verifications_email_idx` ON `(email)`
  - `email_verifications_active_idx` ON `(consumed_at)` partial `WHERE consumed_at IS NULL`
- 一致性：同 `(user_id) WHERE consumed_at IS NULL AND expires_at > NOW()` 至多 1 行；事务内 `UPDATE ... SET consumed_at = NOW() WHERE id=? AND consumed_at IS NULL` 保证。
- 迁移：纯 schema 声明；不写回填或脚本，遵循 CLAUDE.md “One-shot Migration Code”。
- 清理：启动后异步调用 `email_verification_service.purge_expired()`，删除 `consumed_at` 或 `expires_at` 早于 30 天的记录，失败仅记日志。

## 4. 后端

### 4.1 路由（`backend/app/api/email_verification.py`）

- `POST /api/auth/email-verifications/request`
  - Body：`{ "email": "user@example.com" }`
  - 响应：202 `{ "expires_in": 600 }`
- `POST /api/auth/email-verifications/resend`
  - Body：`{ "email": "user@example.com" }`
  - 响应：202 `{ "expires_in": 600, "next_resend_in": 60 }`
  - 副作用：作废旧活跃码后插入新码。
- `POST /api/auth/email-verifications/verify`
  - Body：`{ "email": "user@example.com", "code": "123456" }`
  - 响应：200 `{ "verified": true }` 或 `{ "verified": true, "already": true }`
  - 副作用：`consumed_at = NOW()`、`users.is_verified = TRUE`、`users.is_active = TRUE`。
- 错误响应（统一 `{ code, message, detail? }`）：

| 场景 | HTTP | code |
| --- | --- | --- |
| 邮箱不存在 | 404 | `EMAIL_NOT_FOUND` |
| 邮箱已验证 | 409 | `ALREADY_VERIFIED` |
| 验证码错误（未耗尽） | 400 | `CODE_INVALID`（detail.remaining） |
| 错误次数耗尽 | 410 | `CODE_EXHAUSTED` |
| 验证码过期 | 410 | `CODE_EXPIRED` |
| 限流 | 429 | `RATE_LIMITED`（detail.retry_after） |
| 邮件服务不可用 | 503 | `EMAIL_UNAVAILABLE` |
| 服务端错误 | 500 | `INTERNAL` |

- 新增 `EmailVerificationError` 及子类；在 `backend/app/main.py` 注册 handler。

### 4.2 服务层（`backend/app/services/email_verification_service.py`）

- 常量：
  - `OTP_TTL_SECONDS = 600`
  - `OTP_MAX_ATTEMPTS = 5`
  - `OTP_RESEND_COOLDOWN = 60`
- 公开方法：
  - `issue_for_user(user, request) -> EmailOtpRecord`
    1. 作废同 user 活跃记录；
    2. `secrets.randbelow(1_000_000)` → `"%06d"`；
    3. `INSERT` 新记录；
    4. 调用 `email_service.send_verification_otp_sync(user, code, request)`。
  - `resend(email, request) -> EmailOtpRecord`
    1. 校验 `last_sent_at` 距今 < `OTP_RESEND_COOLDOWN` → 429；
    2. 复用 `issue_for_user` 路径。
  - `verify(email, code, request) -> User`
    1. `SELECT ... WHERE email=? AND consumed_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1 FOR UPDATE`；
    2. `sha256(code + PEPPER).hexdigest()` 与 `code_hash` 比对；
    3. 一致：标记 `consumed_at`、更新 `users.is_verified / is_active`；
    4. 不一致：`attempts += 1`，达上限则 `consumed_at = NOW()`。
  - `purge_expired(retention_days=30) -> int`
- 审计：每次 issue / resend / verify 写 `audit_logs`，事件名 `email.otp.issue / resend / verify`。

### 4.3 与既有组件协作

- `backend/app/auth/users.py:on_after_register`：在 `log_audit(...)` 之后追加 `email_verification_service.issue_for_user(user, request)`，捕获异常仅记日志，不影响注册响应。
- `backend/app/main.py`：
  - `get_auth_router(auth_backend, requires_verification=True)`
  - 删除 `get_verify_router` 及对应 `InvalidVerifyToken / UserAlreadyVerified` 异常 handler 注册；
  - `get_users_router(..., requires_verification=True)`；
  - 挂载 `email_verification_router`；
  - 注册 `EmailVerificationError` 处理器。
- `backend/app/services/email_service.py`：
  - 新增 `send_verification_otp_sync(user, code, request)`：纯文本 + 6 位码 + 10 分钟提示，不含链接。
  - 保留 `send_verification_email_sync`（token 链接）兜底实现。
  - 未配 SMTP 且 `ENV=development` → `logger.info("[DEV OTP] email=%s code=%s ttl=%ss", ...)`，但仍走原 `_send`（`SMTP_HOST=mailpit` 时由 Mailpit 捕获）。
  - 未配 SMTP 且 `ENV=production` + `EMAIL_OTP_SOFT_FAIL=False` → 抛 `EMAIL_UNAVAILABLE`。

### 4.4 限流

- 按 email：
  - `email_otp_request_limiter`：`max_requests=1, window_seconds=60`，key=`email_otp:req:<email>`，作用于 request + resend。
  - `email_otp_verify_limiter`：`max_requests=10, window_seconds=60`，key=`email_otp:verify:<email>`。
- 按 IP 兜底：
  - `email_otp_ip_limiter`：`max_requests=30, window_seconds=60`，key=`email_otp:ip:<addr>`。
- 实现：复用 `backend/app/rate_limit_redis.py:RedisRateLimiter`；无 Redis 时降级 `backend/app/rate_limit.py` 内存版（按 `name` 区分键前缀）。

### 4.5 配置项（`backend/app/core/config.py`）

```python
OTP_TTL_SECONDS: int = 600
OTP_MAX_ATTEMPTS: int = 5
OTP_RESEND_COOLDOWN: int = 60
INNOVOS_OTP_PEPPER: str = ""
EMAIL_OTP_SOFT_FAIL: bool = False
```

- `_enforce_production_settings` 校验：`ENV=production` 时 `INNOVOS_OTP_PEPPER` 必填，启动失败。

### 4.6 回填与回滚

- 启动期幂等 SQL：`UPDATE users SET is_verified=TRUE, is_active=TRUE WHERE is_verified IS NOT TRUE AND id NOT IN (SELECT id FROM users WHERE is_superuser=TRUE)` 不执行；对 `is_superuser=TRUE` 跳过（管理员维持 `is_active=TRUE`）。
- 不引入一次性脚本；不写 alembic data migration。
- 回滚：单 commit 内 `git revert` 即可恢复路由与 `on_after_register`。

## 5. 前端

### 5.1 `VerifyEmailPage`（新增）

- 路径：`/verify-email?email=...`（无 email 参数跳 `/register`）。
- UI：与 `RegisterPage` 卡片风格一致，6 个独立 `input`，粘贴自动拆 6 位，只接受数字。
- 行为：满 6 位自动 POST `verifyEmailOtp`；倒计时 60s 重发；错误显示在卡片顶部；成功后 `navigate('/login?email=' + encodeURIComponent(email))`。
- 状态：纯本地 `useState`，不污染 store。

### 5.2 `RegisterPage`（修改）

- 注册成功 → `navigate('/verify-email?email=' + encodeURIComponent(email))`，不再自动 `login`。
- 错误处理沿用现有 `setError` 模式。

### 5.3 `useAuthStore`（修改）

- `register` 改为仅调 `authApi.register`，**不再** 自动 `login`，注释更新。

### 5.4 `LoginPage`（修改）

- 401 且 `code === 'UserInactive'` → `navigate('/verify-email?email=' + encodeURIComponent(email))`，并提示“请先完成邮箱验证”。
- 其他 401 文案保持。

### 5.5 `api/auth.ts`（新增）

```ts
requestEmailOtp(email: string): Promise<{ expires_in: number }>;
resendEmailOtp(email: string): Promise<{ expires_in: number; next_resend_in: number }>;
verifyEmailOtp(email: string, code: string): Promise<{ verified: true; already?: boolean }>;
```

### 5.6 路由

- `frontend/src/routes/index.tsx`（或 `App.tsx`）注册 `lazyPage(() => import('@/features/auth/VerifyEmailPage'))` → 路径 `/verify-email`，`requireAuth: false`。

### 5.7 状态流

```
RegisterPage                  VerifyEmailPage              LoginPage
   |                              |                            |
   |--POST /register-------------->|                            |
   |  (成功,不登录)               |--POST /email-verifications/verify-->|
   |                              |  200  →  /login?email=...  |
   |                              |                            |--POST /api/auth/jwt/login
   |                              |                            |  200 → /
   |                              |                            |  401 UserInactive
   |                              |<-------- navigate ----------|
   |<-------- navigate -----------|
```

## 6. 错误处理

- 邮件发送失败：SMTP 已配 → 路由仍返回 202（防探测），后台日志记录失败；前端提示“已发送，若未收到请稍后重发”。
- 错误次数耗尽：作废当前记录，引导点击“重发”。
- 验证码过期：`expired_at < NOW()` → 410 `CODE_EXPIRED`，自动启用重发按钮。
- 邮箱不存在：仅 `resend` 返回 404；`verify` 同样 404 防探测，统一文案“若邮箱未注册，请先注册”。
- 已验证用户调 `verify`：返回 200 `{ verified: true, already: true }`，幂等。

## 7. 数据库迁移

- 全部以 `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` 形式写入 `pg_schema.py`。
- 不写回填 / 数据转换 / Alembic data migration。
- 启动期由 `init_db()` 应用 schema 声明；与 `users / api_keys` 等既有表一致。

## 8. 配置与本地开发

- `.env.example` 新增：
  - `SMTP_HOST=mailpit`
  - `SMTP_PORT=1025`
  - `SMTP_FROM_EMAIL=noreply@innovos.local`
  - `SMTP_TLS=false`
  - `INNOVOS_OTP_PEPPER=`（dev 留空、生成随机；prod 必填）
  - `EMAIL_OTP_SOFT_FAIL=true`（dev 默认软失败）
- 启动 Mailpit：`docker compose --profile mail up mailpit`，Web UI `http://localhost:8025`。
- 未配 SMTP 且 `ENV=development` → OTP 明文入 INFO 日志（`[DEV OTP] email=... code=...`）。

## 9. 测试

### 9.1 后端 `backend/tests/test_email_verification.py`

1. `test_register_issues_otp_and_sends_email`
2. `test_verify_success_marks_user_verified`
3. `test_verify_wrong_code_increments_attempts`
4. `test_verify_wrong_code_exhausts_after_5_attempts`
5. `test_verify_expired_code_returns_code_expired`
6. `test_resend_invalidates_previous_code`
7. `test_resend_cooldown_enforced`
8. `test_login_requires_verification`（`is_verified=false` → 401 `UserInactive`）
9. `test_login_succeeds_when_verified`
10. `test_dev_otp_logged_when_smtp_unset`
11. `test_purge_expired_removes_old_records`

### 9.2 前端

- `frontend/src/features/auth/__tests__/RegisterPage.test.tsx`（新增）：注册成功跳 `/verify-email?email=...`。
- `frontend/src/features/auth/__tests__/VerifyEmailPage.test.tsx`（新增）：满 6 位自动 verify、错误提示、重发倒计时 disabled。
- `frontend/src/features/auth/__tests__/LoginPage.test.tsx`（修改）：401 `UserInactive` → 跳 `/verify-email?email=...`。

### 9.3 工具与质量门

- `conftest.py` 提供 `force_verified(user_id)` / `create_user(is_verified=False)`。
- `make test`、`make lint`（tsc --noEmit、ruff、mypy）必须通过。

## 10. 文档

- `docs/architecture.md` 新增“邮箱验证（6 位邮件 OTP）”小节。
- `docs/development.md` 新增“本地查看验证码：Mailpit / 日志”。
- `.env.example` 更新。

## 11. 验收清单（DoD）

- 后端：表与路由、限流、`requires_verification=True`、dev 日志兜底、prod pepper 强制均已落地并由单测覆盖。
- 前端：注册 → 验证 → 登录 路径无自动登录；`tsc --noEmit` 通过。
- 文档 / 部署：`.env.example` 与两份 `docs` 更新；Mailpit 启动可看到验证码。
- `make test && make lint` 全绿。

## 12. 风险与范围外

- 风险：移除 `/api/auth/verify` 路由可能影响外部脚本（无证据存在，记录为后续观察项）。
- 风险：历史 `is_verified=false` 账号被登录拦截 → 启动期不主动回填普通用户；管理员维持现状。
- 范围外：手机号、图形验证码、reset password 改造、OAuth。

## 13. 实施顺序

1. 落表结构与配置项。
2. 写 `email_verification_service` + 单测。
3. 挂载路由 + `main.py` 路由调整 + 移除原生 verify router。
4. 改 `users.py.on_after_register` + `email_service` OTP 通道。
5. 改 `RegisterPage / LoginPage / useAuthStore / api/auth.ts / routes`。
6. 新增 `VerifyEmailPage`。
7. 写前端测试。
8. 更新文档。
9. `make test && make lint`。
