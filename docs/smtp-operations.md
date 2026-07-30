# SMTP 邮件服务运维指南

本文档描述 InnovOS 邮件服务（SMTP）的**配置、调试、故障排查、密钥轮换**流程。涵盖邮箱验证码（OTP）下发、密码重置邮件、邮箱验证邮件三条业务链路。

---

## 1. 概述

InnovOS 通过标准 SMTP 协议外发三类邮件：

| 邮件类型 | 触发点 | 收件人 | 模板 |
|----------|--------|--------|------|
| 邮箱验证码（6 位 OTP） | 用户注册 / 重发 | 邮箱所有者 | 内嵌 6 位数字，10 分钟有效 |
| 邮箱验证链接 | 注册（备用） | 邮箱所有者 | `/verify-email?token=xxx` 链接 |
| 密码重置验证码（6 位 OTP） | 用户忘记密码 | 邮箱所有者 | 仅含 6 位验证码，无 URL；10 分钟有效 |

**实现位置：**
- 邮件服务：`backend/app/services/email_service.py`
- 验证码业务：`backend/app/services/email_verification_service.py`
- 路由挂载：`backend/app/main.py:245-254`
- 前端路由：`frontend/src/routes/index.tsx:35-37`

**`PUBLIC_URL` 的作用：** 邮件正文里的链接必须拼接 `settings.PUBLIC_URL` + 前端路由路径。**`PUBLIC_URL` 应设置为前端可访问的根 URL**（如 `https://app.example.com`），否则用户点链接会跳错地方。

---

## 2. 配置

### 2.1 SMTP 字段定义

`.env` 文件末尾的 SMTP 段：

```env
SMTP_HOST=                     # SMTP 服务器域名
SMTP_PORT=465                  # 端口（465 SSL / 587 STARTTLS / 25 明文）
SMTP_USER=                     # SMTP 登录用户名（完整邮箱地址）
SMTP_PASSWORD=                 # SMTP 授权码（不是登录密码！）
SMTP_FROM_EMAIL=               # 发件人邮箱（通常与 SMTP_USER 一致）
SMTP_SSL=true                  # 端口 465 → true；其他端口 → false
SMTP_TLS=false                 # 端口 587 → true；端口 465 → false
EMAIL_OTP_SOFT_FAIL=true       # 生产必须设为 false；dev 软失败可吞错
```

**SSL vs TLS 不能同时为 true**：

| 端口 | SSL | TLS | 加密方式 |
|------|-----|-----|----------|
| 465  | ✅ true | ❌ false | 隐式 SSL（连接即加密） |
| 587  | ❌ false | ✅ true | STARTTLS（明文握手后升级） |
| 25   | ❌ false | ❌ false | 明文（不推荐） |

### 2.2 各邮箱服务商配置模板

#### QQ 邮箱（推荐，国内最稳）

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=123456789@qq.com
SMTP_PASSWORD=<QQ 后台授权码，16 位字符串>
SMTP_FROM_EMAIL=123456789@qq.com
SMTP_SSL=true
SMTP_TLS=false
```

**获取授权码：** 登录 https://mail.qq.com → 设置 → 账号 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 → 开启 POP3/SMTP → 扫码发短信 → 复制授权码。

#### 163/126 邮箱

```env
SMTP_HOST=smtp.163.com          # 126 改成 smtp.126.com
SMTP_PORT=465
SMTP_USER=yourname@163.com
SMTP_PASSWORD=<163 后台授权码>
SMTP_FROM_EMAIL=yourname@163.com
SMTP_SSL=true
SMTP_TLS=false
```

**获取授权码：** https://dashi.163.com/ → 邮箱设置 → POP3/SMTP/IMAP → 开启 POP3/SMTP → 扫码 → 复制授权码。

#### Gmail（需翻墙，推荐度低）

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourname@gmail.com
SMTP_PASSWORD=<Google 应用专用密码，16 位>
SMTP_FROM_EMAIL=yourname@gmail.com
SMTP_SSL=false
SMTP_TLS=true
```

**获取密码：** Google 账号 → 安全 → 两步验证 → 应用专用密码 → 生成。

#### Mailpit（本地调试，零成本）

```bash
docker run -d --name mailpit --restart unless-stopped --network=host \
  axllent/mailpit:latest
```

```env
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@innovos.local
SMTP_SSL=false
SMTP_TLS=false
```

浏览器访问 `http://127.0.0.1:8025` 查看所有发出的邮件。**注意：** InnovOS 用 `network_mode: host`，Mailpit 必须用 `--network=host` 启动，否则端口不通。

---

## 3. 三层降级机制

`email_service.py` 实现了一套三级降级，**确保开发与生产都能跑通**：

### Level 1 — SMTP 正常（生产形态）
- 配置 `SMTP_HOST/PORT/USER/PASSWORD`，`SMTP_SSL/TLS` 选一
- 邮件通过 `smtplib` 投递到第三方 SMTP
- 推荐：QQ / 163 / Gmail / SendGrid / Mailgun / 阿里云邮件推送

### Level 2 — Dev 模式 SMTP 留空
仅当 `ENVIRONMENT=development` 时生效：
- 邮箱验证码（OTP）→ 打印到 backend 日志：`[DEV OTP] email=xxx code=123456 ttl=600s`
- 验证邮件（verify）→ 打印到日志：`[DEV VERIFY] email=xxx url=http://localhost/verify-email?token=...`
- 重置邮件（reset）→ 打印到日志：`[DEV RESET] email=xxx url=http://localhost/reset-password?token=...`

**生产模式（`ENV=production`）不留 SMTP 会启动失败**（fail-fast）。这是 `email_service.py` 第 90-91 行的保护逻辑。

### Level 3 — 软失败开关
`EMAIL_OTP_SOFT_FAIL=true` 时，SMTP 投递失败只打 ERROR 日志不抛异常；
`EMAIL_OTP_SOFT_FAIL=false` 时，抛 `EmailUnavailable` 异常（推荐生产）。

---

## 4. 端到端冒烟测试

每次改 SMTP 配置或升级邮件服务后，跑一次完整流程：

```bash
# 4.1 请求密码重置 OTP → 应收到 6 位验证码
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/request-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@example.com"}'

# 4.2 验证 OTP → 返回 reset_token（替换 CODE 为实际收到的 6 位数）
RESP=$(curl -s -X POST http://127.0.0.1:8000/api/auth/password-reset/verify \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@example.com","code":"123456"}')
TOKEN=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('reset_token',''))")

# 4.3 用 reset_token 改密
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/set-password \
  -H "Content-Type: application/json" \
  -d "{\"reset_token\":\"$TOKEN\",\"new_password\":\"newpass1234\"}"
```

清理测试账号（**一次性脚本，用完即丢**）：

```bash
cd backend && .venv/bin/python -c "
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

## 5. 故障排查

### 5.1 错误速查表

| 错误信息 | 根因 | 修复 |
|----------|------|------|
| `Connection refused` | host/port 错或防火墙拦截 | telnet `SMTP_HOST SMTP_PORT` 验证可达 |
| `535 Authentication failed` | 授权码错或没在后台开 SMTP 服务 | 去邮箱后台重新生成授权码 |
| `530 Error: Need Ehlo` | SSL/TLS 配置错 | 端口 465 → `SSL=true TLS=false`；587 → 反之 |
| `554 DT:SPM` (QQ) | QQ 反垃圾邮件规则触发 | 降低发信频率；调整邮件正文避免触发规则 |
| `SSL: WRONG_VERSION_NUMBER` | SMTP_SSL/SMTP_TLS 错配 | 见 2.1 节端口对照表 |
| 后端日志 `邮件发送失败 to=xxx` | 真投递失败 | 检查错误堆栈、SMTP 服务商状态 |
| 接口返回 202 但邮箱没收到 | 邮件被拦或服务商拒发 | 检查垃圾邮件夹；查 backend 日志是否有错误 |

### 5.2 邮件内容路径错误（前端路由不匹配）

历史 Bug：原代码邮件链接路径是 `/verify?token=xxx`，但前端路由表只有 `/verify-email`，导致邮件链接点开 → NotFoundPage。

**当前正确路径**（见 `email_service.py`）：
- 验证：`{PUBLIC_URL}/verify-email?token=...`（用于邮箱验证链接）
- 重置：纯 6 位 OTP 邮件，无 URL（`/api/auth/password-reset/verify` 验证）

如果改了前端路由，必须同步更新 `email_service.py:54-72` 的链接拼接。

### 5.3 验证码收不到但后端 200

最常见的三种情况：

1. **QQ/163 首次发信被防垃圾拦截** → 让收件人检查垃圾邮件夹；或加白名单
2. **域名解析失败** → 检查 `PUBLIC_URL` 是否能正常解析
3. **PROD 模式但只配了 dev 兜底** → `EMAIL_OTP_SOFT_FAIL=true` 会吞掉 SMTP 异常，backend 日志里查 `邮件发送失败`

### 5.4 用 Mailpit 隔离排查

调试时切到 Mailpit（5 分钟内可来回切换），可绕过真实邮箱服务商的不可控变量：

```bash
# 切到 Mailpit
sed -i 's|^SMTP_HOST=.*|SMTP_HOST=localhost|' .env
sed -i 's|^SMTP_PORT=.*|SMTP_PORT=1025|' .env
sed -i 's|^SMTP_SSL=.*|SMTP_SSL=false|' .env
sed -i 's|^SMTP_TLS=.*|SMTP_TLS=false|' .env
docker compose restart backend

# 切回正式 SMTP（QQ/163...）
# 直接编辑 .env 把对应字段改回去，然后重启
```

---

## 6. 安全与密钥管理

### 6.1 授权码管理

**SMTP 授权码 = 邮箱账号的控制权**，等同于登录密码。

- ⚠️ **不写入 git**：确认 `.gitignore` 包含 `.env`（项目默认已包含）
- ⚠️ **不在日志输出**：`email_service.py` 已避免记录明文密码；如未来加日志功能必须脱敏
- ⚠️ **不通过聊天工具明文传输**：开发协作时用 1Password / Vault / K8s Secret 共享
- ⚠️ **定期轮换**：若怀疑泄露立即在邮箱后台作废旧码，生成新码

### 6.2 授权码轮换步骤

1. **登录邮箱后台**（如 https://mail.qq.com）→ 生成新授权码
2. **更新 Secret Manager**（K8s Secret / Docker Secret / Vault），不要改 `.env` 后 commit
3. **重启 backend** 让新授权码生效
4. **冒烟测试**（见第 4 节）
5. **邮箱后台作废旧授权码**（避免泄露窗口期被滥用）

### 6.3 反垃圾邮件最佳实践

- 发件人域名配置 SPF / DKIM / DMARC 记录（DNS）
- 邮件正文避免纯图片、纯链接、低文本量（容易被识别为垃圾）
- 控制单位时间发信量：QQ 一般 ≤ 500/天，163 ≤ 200/天
- 主题避免营销词汇（"免费""限时""中奖"等）
- 给用户提供「退订」链接（生产场景必须）
- 密码重置邮件只含 6 位纯数字验证码，不放 URL（降低被钓鱼滥用的风险）

---

## 7. 监控告警建议

生产部署时建议加以下监控点：

| 指标 | 阈值 | 告警渠道 |
|------|------|----------|
| 5 分钟内 SMTP 投递失败率 | > 10% | 企业微信 / Slack / 钉钉 |
| 单 IP 触发 `EmailNotFound` / `InvalidResetSession` 次数 | > 50/h | 防探测 / 防滥用告警 |
| `email_verifications` 表 24h `purpose=password_reset` 新增数 | 突增 3x | 防滥用告警 |
| SMTP 端口连通性（`SMTP_HOST:SMTP_PORT`） | 连通失败 | 立即告警 |
| `OTPRateLimited` / `InvalidResetSession` 抛出频次 | > 100/h | 防爆破告警 |

---

## 8. 常见运维操作

### 8.1 切换 SMTP 服务商（QQ → 163）

```bash
# 1. 备份当前 .env
cp .env .env.bak.$(date +%Y%m%d)

# 2. 编辑 .env，把 SMTP_HOST/USER/PASSWORD/FROM_EMAIL 改成 163 的值
vim .env

# 3. SSL/TLS 配置通常一致（都用 465/SSL），无需调整

# 4. 重启 backend
docker compose restart backend

# 5. 冒烟测试（见第 4 节）
```

### 8.2 清理过期的验证码

```sql
-- 手动清理 7 天前已消费 / 30 天前已过期的验证码
DELETE FROM email_verifications
WHERE (consumed_at IS NOT NULL AND consumed_at < NOW() - INTERVAL '7 days')
   OR (expires_at < NOW() - INTERVAL '30 days');
```

`EmailVerificationService.purge_expired()`（`email_verification_service.py:137-147`）已实现此逻辑，可用 cron 每日触发。

### 8.3 紧急关闭邮件外发

生产事故时如需紧急关闭邮件外发（防滥发或服务商挂掉）：

```env
SMTP_HOST=
```

- dev 模式：验证码会落到 backend 日志，流程仍可走通
- prod 模式：启动时 `EMAIL_OTP_SOFT_FAIL=true` 软失败；`false` 则发邮件接口 503

---

## 9. 相关文件索引

| 文件 | 作用 |
|------|------|
| `backend/app/services/email_service.py` | SMTP 投递、三级降级 |
| `backend/app/services/email_verification_service.py` | OTP 生成、验证、清理、reset_session 管理 |
| `backend/app/api/email_verification.py` | 邮箱验证 OTP 路由（`/api/auth/email-verifications/*`） |
| `backend/app/api/password_reset.py` | 密码重置 OTP 路由（`/api/auth/password-reset/*`） |
| `backend/app/exceptions/password_reset.py` | `InvalidResetSession` / `WeakPassword` 异常 |
| `backend/app/main.py:245-260` | FastAPI Users reset + 自研 verify + password-reset 路由挂载 |
| `backend/app/auth/users.py:45-57` | `on_after_forgot_password` / `on_after_request_verify` 回调 |
| `backend/app/core/config.py:88-112` | SMTP / OTP / RESET_SESSION 配置字段定义 |
| `frontend/src/api/auth.ts` | 前端邮件 API 客户端（含 3 个新的密码重置 OTP 方法） |
| `frontend/src/features/auth/{ForgotPasswordPage,VerifyResetOtpPage,ResetPasswordPage,VerifyEmailPage}.tsx` | 前端邮件流程页面 |
| `frontend/src/routes/index.tsx:35-37` | 前端路由注册 |
| `backend/tests/test_email_service.py` | 邮件服务回归测试 |
| `backend/tests/test_password_reset_otp.py` | 密码重置 OTP 链路测试（6+ 个测试） |