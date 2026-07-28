# InnovOS 认证体系重构设计：全量采用 FastAPI Users

- **日期**: 2026-07-28
- **状态**: 已确认，待实施
- **作者**: HowardChouX
- **关联**: InnovOS `dev2` 分支

## 1. 目标与范围

### 1.1 顶层目标

全量采用 FastAPI Users 重构 InnovOS 的用户管理与认证体系。所有与 FastAPI Users 标准用法冲突的现有规则、代码、数据结构都让路并修正。

### 1.2 范围

- 后端认证层：替换 `app/auth.py`、`app/api/deps.py`、`app/core/security.py` 的手写实现
- 用户表：迁移到 SQLAlchemy ORM + Alembic 管理（仅 `users` 表，其余业务表不动）
- 前端：登录/注册表单改 email，新增忘记密码/重置密码/邮箱验证页面
- 数据迁移：清除 `id=0` 幽灵管理员，`email` 升为登录主键

### 1.3 不在范围内

- 其余 20+ 张业务表的 ORM 迁移（保持 raw psycopg2）
- 异步化（保持同步执行模型）
- OAuth2 第三方登录（当前不需要）

## 2. 已确认的架构决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| A. 重构范围 | 全量采用 FastAPI Users，冲突规则让路 | 顶层目标 |
| B. 执行模型 | 同步 | 与现有代码风格一致，改动可控 |
| C. 管理员模型 | 进 DB，`.env` 仅首次 seed，清除 `id=0` 幽灵 | FastAPI Users 的 `is_superuser` 标准机制 |
| D. Token 策略 | JWT + 保留 `token_version` 撤销机制 | 保留现有撤销能力，避免 Redis 单点故障 |
| E. 登录标识 | email 登录，phone 为档案字段 | FastAPI Users 标准模式，解锁邮箱验证/重置能力 |

### 2.1 关键设计点

1. **`token_version` 织入方式**：子类化 `JWTStrategy`，override `read_token`/`write_token`，撤销逻辑集中在 strategy 内，上层零改动。
2. **数据迁移策略**：Alembic 只管 DDL（幂等 schema 声明），data backfill 走一次性脚本（运行后删除），符合 AGENTS.md 的 One-shot Migration 规则。
3. **邮件基础设施**：开发环境 Mailpit，生产环境 SMTP，新增 `app/services/email_service.py`。

## 3. 总体架构

重构后的认证体系分为四层，每层职责单一、通过明确接口通信：

```
┌─────────────────────────────────────────────────────────┐
│  API 路由层 (app/api/)                                  │
│  auth.py / users.py / admin/users.py                    │
│  依赖注入: current_active_user / current_superuser      │
├─────────────────────────────────────────────────────────┤
│  FastAPI Users 层 (app/auth/)                           │
│  users.py    - UserManager（生命周期回调 + 审计）        │
│  backend.py  - JWTStrategy(定制) + CookieTransport      │
│  instance.py - FastAPIUsers 实例 + 依赖工厂              │
├─────────────────────────────────────────────────────────┤
│  ORM 层 (app/db/)  ← 新增                               │
│  base.py     - SQLAlchemy declarative base              │
│  session.py  - 同步 engine + sessionmaker               │
│  models.py   - User ORM（SQLAlchemyBaseUserTable）      │
├─────────────────────────────────────────────────────────┤
│  迁移层 (backend/alembic/)  ← 新增                      │
│  仅管 users 表 DDL；data backfill 走一次性脚本           │
├─────────────────────────────────────────────────────────┤
│  基础服务                                                │
│  email_service.py ← 新增（Mailpit/SMTP）                │
│  audit.py（复用）  rate_limit_redis.py（复用）          │
└─────────────────────────────────────────────────────────┘
```

### 3.1 关键边界

- **ORM 层只管 `users` 表**。其余 20+ 张业务表保持 raw psycopg2 + `pg_schema.py` 模式。两套数据访问模式并存：用户/认证走 ORM，业务数据走 raw SQL。
- **删除旧实现**：`app/auth.py`（dict 版 `get_current_user`）、`app/api/deps.py`（User 版）、`app/core/security.py` 全部删除。全局 25+ 文件统一改用 `app.auth.instance` 导出的 `current_active_user` / `current_superuser`。
- **`token_version` 撤销逻辑封装在 `InnovOSJWTStrategy` 内**，对上层透明。

### 3.2 登录数据流

```
POST /api/auth/jwt/login
  -> FastAPI Users auth_router
  -> UserManager.authenticate（查 ORM User，pwdlib 校验密码）
  -> InnovOSJWTStrategy.write_token（签 JWT，注入 token_version）
  -> CookieTransport.set_cookie（写 __Host-token）
  -> on_after_login 回调（写 audit_log）
  -> 返回 {user: UserRead}
```

## 4. 数据模型与 ORM

### 4.1 `users` 表 schema 变更

| 字段 | 现状 | 重构后 | 说明 |
|---|---|---|---|
| `id` | INTEGER PK | INTEGER PK | 不变（`IntegerIDMixin`） |
| `email` | TEXT DEFAULT '' | TEXT UNIQUE NOT NULL | 升为登录主键 |
| `hashed_password` | `password_hash` TEXT | `hashed_password` TEXT | 改名对齐 FastAPI Users |
| `is_active` | INTEGER DEFAULT 1 | BOOLEAN DEFAULT TRUE | 类型修正 |
| `is_superuser` | 无 | BOOLEAN DEFAULT FALSE | 新增，认证层超管标志 |
| `is_verified` | 无 | BOOLEAN DEFAULT FALSE | 新增，邮箱验证标志 |
| `username` | TEXT UNIQUE NOT NULL | TEXT（可空，显示名） | 降级为可选昵称 |
| `phone` | 无 | TEXT（可空） | 新增，档案字段，不参与登录 |
| `role` | TEXT DEFAULT 'user' | TEXT DEFAULT 'user' | 保留，业务角色 |
| `token_version` | INTEGER DEFAULT 0 | INTEGER DEFAULT 0 | 保留，撤销机制 |
| `created_at` | TEXT | TIMESTAMP DEFAULT NOW() | 类型升级 |
| `updated_at` | TEXT | TIMESTAMP | 保留 |

### 4.2 `role` 与 `is_superuser` 的关系

- `is_superuser`：FastAPI Users 认证层超级用户标志，控制能否访问 `current_superuser` 保护的端点（用户管理、撤销 token 等）。
- `role`：业务层角色（`admin`/`user`，未来可扩展 `teacher`/`student`），控制业务权限。
- 管理员：`is_superuser=True AND role='admin'`。
- 普通用户：`is_superuser=False AND role='user'`。
- 两者正交，不混用。

### 4.3 ORM 模型

```python
# app/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# app/db/models.py
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP
from app.db.base import Base

class User(SQLAlchemyBaseUserTable, Base):
    __tablename__ = "users"
    # SQLAlchemyBaseUserTable 提供: id, email, hashed_password,
    #   is_active, is_superuser, is_verified
    username = Column(String(100), nullable=True)   # 显示名，可空
    phone = Column(String(20), nullable=True)        # 档案字段，不参与登录
    role = Column(String(20), default="user")        # 业务角色
    token_version = Column(Integer, default=0)       # 撤销机制
```

### 4.4 SQLAlchemy session

```python
# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10, max_overflow=20, pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

此 session 替代现有 `get_db_dep`（psycopg2 连接池），但**仅用于认证/用户表**。业务路由的 `SessionDep` 仍指向现有 psycopg2 `db_session()`，两者共存。

### 4.5 Schemas

```python
# app/auth/schemas.py
from fastapi_users import schemas
from pydantic import Field

class UserRead(schemas.BaseUser[int]):
    username: str | None = None
    phone: str | None = None
    role: str = "user"

class UserCreate(schemas.BaseUserCreate):
    # email, password 从 BaseUserCreate 继承
    username: str | None = None
    phone: str = Field(default=None, description="手机号，仅档案存储")

class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None
    phone: str | None = None
```

## 5. FastAPI Users 核心组件

### 5.1 UserManager

```python
# app/auth/users.py
from fastapi import Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi_users.exceptions import InvalidPasswordException
from app.core.config import settings
from app.db.models import User
from app.services.email_service import email_service
from app.audit import log_audit

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(self, user: User, request: Request | None = None):
        log_audit(user.id, user.email, "user.register", "user", str(user.id), {},
                  request.client.host if request else "")
        await email_service.send_verification_email(user, request)

    async def on_after_login(self, user: User, request: Request | None = None, response=None):
        log_audit(user.id, user.email, "user.login", "user", str(user.id), {},
                  request.client.host if request else "")

    async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None):
        await email_service.send_reset_password_email(user, token)

    async def on_after_request_verify(self, user: User, token: str, request: Request | None = None):
        await email_service.send_verification_email_with_token(user, token)

    async def on_after_verify(self, user: User, request: Request | None = None):
        log_audit(user.id, user.email, "user.verify", "user", str(user.id), {}, "")

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(reason="密码至少 8 位")
```

### 5.2 定制 JWTStrategy（token_version 织入）

```python
# app/auth/strategy.py
from fastapi_users.authentication import JWTStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager

class InnovOSJWTStrategy(JWTStrategy):
    """JWT + token_version 撤销校验。"""

    async def read_token(self, token, user_manager: BaseUserManager):
        if token is None:
            return None
        try:
            data = decode_jwt(token, self.decode_key, self.token_audience,
                              algorithms=[self.algorithm])
            user_id = data.get("sub")
            token_version = data.get("token_version", 0)
            if user_id is None:
                return None
        except Exception:
            return None
        try:
            parsed_id = user_manager.parse_id(user_id)
            user = await user_manager.get(parsed_id)
        except Exception:
            return None
        # token_version 校验：不匹配则视为已撤销
        if user and getattr(user, "token_version", 0) != token_version:
            return None
        return user

    async def write_token(self, user) -> str:
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "token_version": getattr(user, "token_version", 0),
        }
        return generate_jwt(data, self.encode_key, self.lifetime_seconds,
                            algorithm=self.algorithm)
```

### 5.3 认证后端（CookieTransport）

```python
# app/auth/backend.py
from fastapi_users.authentication import (
    AuthenticationBackend, CookieTransport,
)
from app.auth.strategy import InnovOSJWTStrategy
from app.core.config import settings

cookie_transport = CookieTransport(
    cookie_name="__Host-token",
    cookie_max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax",
)

def get_jwt_strategy() -> InnovOSJWTStrategy:
    return InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
```

`__Host-` 前缀要求 cookie 设 `Secure`、`Path=/`、无 `Domain`。`CookieTransport` 支持 `cookie_secure=True` 且不设 domain，符合 `__Host-` 规范。

### 5.4 FastAPIUsers 实例与依赖工厂

```python
# app/auth/instance.py
from fastapi_users import FastAPIUsers
from app.auth.backend import auth_backend
from app.auth.users import UserManager, get_user_manager
from app.auth.schemas import UserRead, UserCreate, UserUpdate
from app.db.models import User

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
```

### 5.5 路由挂载

```python
# app/main.py
app_.include_router(
    fastapi_users.get_auth_router(auth_backend),
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
app_.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/api/auth", tags=["auth"],
)
app_.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users", tags=["users"],
)
```

### 5.6 路由变化对照

| 旧路由 | 新路由 | 备注 |
|---|---|---|
| `POST /api/auth/register` | `POST /api/auth/register` | 字段 username -> email + phone |
| `POST /api/auth/login` | `POST /api/auth/jwt/login` | FastAPI Users 标准路径，`OAuth2PasswordRequestForm` |
| `POST /api/auth/logout` | `POST /api/auth/jwt/logout` | |
| `GET /api/auth/me` | `GET /api/users/me` | 移到 users router |
| `PUT /api/users/me/password` | `POST /api/auth/reset-password` | 或保留 custom 改密 |
| - | `POST /api/auth/forgot-password` | 新增 |
| - | `POST /api/auth/request-verify-token` | 新增 |
| - | `POST /api/auth/verify` | 新增 |
| `GET/PUT/DELETE /api/admin/users/*` | 保留自定义 | FastAPI Users 的 users_router 不够，保留现有 admin router |

## 6. 数据迁移与 One-shot 规则调和

### 6.1 迁移分类

| 类型 | 管理方式 | 符合 One-shot 规则 |
|---|---|---|
| **DDL（schema 声明）** | Alembic revision（版本化） | 是，"可重复的纯 schema 声明" |
| **Data backfill（数据回填）** | 一次性 Python 脚本，运行后删除 | 是 |

### 6.2 Alembic DDL 迁移

Alembic 只负责 `users` 表的 schema 变更，一个 revision：

```python
# alembic/versions/0001_users_fastapi_users_schema.py
def upgrade():
    # 1. 加新列
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), server_default=sa.false()))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default=sa.false()))
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))

    # 2. 改列类型（is_active INTEGER -> BOOLEAN）
    op.alter_column('users', 'is_active',
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        postgresql_using='is_active::boolean')

    # 3. email 加唯一约束 + NOT NULL
    op.alter_column('users', 'email', existing_type=sa.Text(), nullable=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 4. username 放宽为可空
    op.alter_column('users', 'username', existing_type=sa.Text(), nullable=True)
    op.drop_index('ix_users_username', table_name='users')
    op.create_index('ix_users_username', 'users', ['username'])

def downgrade():
    ...
```

`password_hash` -> `hashed_password` 的列改名在 data backfill 脚本里做（`RENAME COLUMN`，单语句，安全），不在 DDL 里做。

### 6.3 一次性 Data Backfill 脚本

```python
# scripts/migrate_users_to_fastapi_users.py
"""
一次性迁移脚本：把 users 表数据从旧 schema 迁移到 FastAPI Users schema。
运行后删除。不留在生产启动路径。

步骤：
1. 列名迁移：password_hash -> hashed_password（RENAME COLUMN）
2. role='admin' -> is_superuser=True
3. email 为空的用户补占位邮箱 {username}@local.invalid
4. user_id=0 的幽灵管理员引用归并到真实管理员 id
5. 删除 id=0 幽灵行
6. seed 真实管理员（从 .env，is_superuser=True）
"""
```

关键步骤：

1. **列名迁移**：`ALTER TABLE users RENAME COLUMN password_hash TO hashed_password`
2. **管理员标志**：`UPDATE users SET is_superuser = TRUE WHERE role = 'admin'`
3. **email 补全**：`UPDATE users SET email = username || '@local.invalid' WHERE email = '' OR email IS NULL`
4. **幽灵管理员归并**：所有 `user_id=0` 的记录（tasks、audit_log、evaluations、feedbacks、notifications）`UPDATE ... SET user_id = <真实管理员id>`
5. **删幽灵行**：`DELETE FROM users WHERE id = 0`
6. **seed 真实管理员**：用 `INNOVOS_ADMIN_USER`/`INNOVOS_ADMIN_PASSWORD` 创建 `is_superuser=True` 的真实用户（如果不存在）

此脚本在部署时手动运行一次，运行后从仓库删除。Alembic 里留一个空 revision 标记 "data migration done"。

### 6.4 `pg_schema.py` 调整

- `init_users()` 和 `seed_admin_user()` **删除**（users 表由 Alembic 接管）
- 其余 20+ 张表的 `init_*` 函数保留不动
- `init_all_tables()` 中移除 `init_users(db)` 和 `seed_admin_user(db)` 调用

### 6.5 启动流程变更

**首次部署（手动）：**
```
alembic upgrade head
python scripts/migrate_users_to_fastapi_users.py  # 用完删
```

**每次启动（自动）：**
```
alembic upgrade head              # 幂等，已应用则跳过
init_db() -> init_all_tables()    # 其余业务表（不含 users）
seed_admin_user_if_missing()      # 幂等 seed 管理员（从 .env，ORM 查询）
```

`seed_admin_user_if_missing()` 保留在启动路径，但改为通过 ORM 查询（`SELECT ... WHERE is_superuser=TRUE`），仅在无超管时创建。这是幂等 seed，符合规则。

### 6.6 对 AGENTS.md / CLAUDE.md 的规则修正

补充一条规则（精确化，非推翻）：

> **Alembic 迁移规则**：Alembic 仅用于 DDL（schema 声明）的版本化管理，每个 revision 必须是幂等的纯声明。Data backfill（数据回填、列重命名带数据迁移、FK 引用归并）仍遵循 One-shot 规则：写成一次性独立脚本，运行后删除，不留在仓库和启动路径。

## 7. 错误处理

FastAPI Users 自带异常体系，需接入 InnovOS 全局异常处理和中文错误信息要求（AGENTS.md:159）。

| FastAPI Users 异常 | HTTP 状态 | InnovOS 中文信息 |
|---|---|---|
| `UserAlreadyExists` | 400 | "该邮箱已注册" |
| `InvalidID` | 400 | "无效的用户 ID" |
| `UserNotExists` | 404 | "用户不存在" |
| `UserInactive` | 400 | "用户已被禁用" |
| `UserAlreadyVerified` | 400 | "用户已验证" |
| `InvalidVerifyToken` | 400 | "无效的验证链接" |
| `InvalidResetPasswordToken` | 400 | "无效的重置链接" |
| `InvalidPasswordException` | 400 | 自定义 reason（如"密码至少 8 位"） |
| `PasswordInvalid` | 400 | "密码错误" |

```python
# app/auth/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_users import exceptions as fu_exceptions

EXCEPTION_MAP = {
    fu_exceptions.UserAlreadyExists: (400, "该邮箱已注册"),
    fu_exceptions.UserNotExists: (404, "用户不存在"),
    fu_exceptions.UserInactive: (400, "用户已被禁用"),
    fu_exceptions.UserAlreadyVerified: (400, "用户已验证"),
    fu_exceptions.InvalidVerifyToken: (400, "无效的验证链接"),
    fu_exceptions.InvalidResetPasswordToken: (400, "无效的重置链接"),
    fu_exceptions.InvalidPasswordException: (400, None),  # 用 reason
}

async def fastapi_users_exception_handler(request: Request, exc: Exception):
    for exc_type, (status, msg) in EXCEPTION_MAP.items():
        if isinstance(exc, exc_type):
            if msg is None:
                msg = getattr(exc, "reason", "密码不符合要求")
            return JSONResponse(status_code=status, content={"detail": msg})
    return JSONResponse(status_code=400, content={"detail": "认证错误"})
```

在 `main.py` 注册所有 FastAPI Users 异常到该 handler。

## 8. 测试策略

### 8.1 测试基础设施

```python
# tests/conftest.py（补充）
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.session import get_session

@pytest.fixture
def test_db():
    engine = create_engine("postgresql://test:test@localhost:5432/test_innovos")
    Base.metadata.create_all(engine)  # 只建 users 表
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def client(test_db):
    app_.dependency_overrides[get_session] = lambda: test_db
    yield TestClient(app_)
    app_.dependency_overrides.clear()
```

### 8.2 测试文件

| 测试文件 | 覆盖内容 |
|---|---|
| `test_auth_register.py` | 注册成功、邮箱重复、密码过短、phone 可选 |
| `test_auth_login.py` | 登录成功、密码错误、用户不存在、禁用用户 |
| `test_auth_logout.py` | 登出后 cookie 清除 |
| `test_auth_verify.py` | 请求验证、验证成功、token 无效、已验证 |
| `test_auth_reset_password.py` | 忘记密码、重置成功、token 无效 |
| `test_auth_token_version.py` | token_version 撤销：管理员撤销后旧 token 失效 |
| `test_users_me.py` | GET/PATCH /api/users/me |
| `test_admin_users.py` | 管理员 CRUD、撤销 token、权限校验 |
| `test_superuser_guard.py` | 非管理员访问 admin 端点返回 403 |

### 8.3 测试纪律

每个端点先写测试（红），再实现（绿），再重构。认证相关代码必须测试覆盖。现有 `test_api_auth.py`、`test_core_auth.py`、`test_core_security.py`、`test_seed_data.py` 需重写（旧实现已删）。

## 9. 前端适配

### 9.1 API 客户端改动

```typescript
// frontend/src/api/auth.ts
export const authApi = {
  register(email: string, password: string, phone?: string, username?: string) {
    return apiRequest<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, phone, username }),
    });
  },

  login(email: string, password: string) {
    return apiRequest<AuthResponse>('/api/auth/jwt/login', {
      method: 'POST',
      body: JSON.stringify({ username: email, password }),
    });
  },

  logout() {
    return apiRequest('/api/auth/jwt/logout', { method: 'POST' });
  },

  me() {
    return apiRequest<AuthUser>('/api/users/me');
  },

  // 新增
  forgotPassword(email: string) {
    return apiRequest('/api/auth/forgot-password', {
      method: 'POST', body: JSON.stringify({ email }),
    });
  },
  resetPassword(token: string, password: string) {
    return apiRequest('/api/auth/reset-password', {
      method: 'POST', body: JSON.stringify({ token, password }),
    });
  },
  requestVerify(email: string) {
    return apiRequest('/api/auth/request-verify-token', {
      method: 'POST', body: JSON.stringify({ email }),
    });
  },
  verify(token: string) {
    return apiRequest('/api/auth/verify', {
      method: 'POST', body: JSON.stringify({ token }),
    });
  },
};
```

**注意**：FastAPI Users 的登录端点用 `OAuth2PasswordRequestForm`，字段名是 `username`/`password`（表单字段，非 JSON body）。前端需用 `application/x-www-form-urlencoded` 发送，`username` 字段填邮箱值。这是一处需要特别注意的契约差异。

### 9.2 AuthUser 类型改动

```typescript
interface AuthUser {
  id: number;
  email: string;            // 主键
  username: string | null;  // 可空显示名
  phone: string | null;     // 档案字段
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}
```

### 9.3 页面改动

| 页面 | 改动 |
|---|---|
| 登录页 | `username` 输入框 -> `email` 输入框，label 改"邮箱" |
| 注册页 | `username` -> `email`（必填）+ `phone`（必填）+ `username`（可选昵称） |
| 新增"忘记密码"页 | 输入邮箱 -> 发送重置链接 |
| 新增"重置密码"页 | 输入新密码 -> 提交 token + password |
| 新增"邮箱验证"提示页 | 注册后提示查收验证邮件 |
| `useAuthStore` | `user` 接口字段调整，`isAdmin` 改为 `is_superuser` |

### 9.4 cookie 机制不变

`__Host-token` cookie 名和属性保持不变，前端 `credentials: 'include'` 不变，`client.ts` 零改动。

## 10. 依赖变更

```toml
# backend/pyproject.toml 新增
"fastapi-users[sqlalchemy] >= 14.0",
"fastapi-users-db-sqlalchemy >= 7.0",
"sqlalchemy >= 2.0",
"alembic >= 1.13",
"pwdlib[argon2,bcrypt] >= 0.3",   # 替代直接 bcrypt
# 移除
# "bcrypt"  (由 pwdlib 承载)
# "python-jose"  (由 pyjwt 承载, FastAPI Users 用 pyjwt)
```

## 11. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| `users` 表 schema 变更破坏 FK | 高 | Alembic DDL 在事务内完成；backfill 先归并引用再删行 |
| `id=0` 幽灵行删除影响 FK | 高 | backfill 先把 `user_id=0` 引用改为真实管理员 id |
| 25+ 文件依赖替换遗漏 | 中 | `rg get_current_user` 全量扫描 + mypy 类型检查兜底 |
| 前端 cookie 名称/域变化 | 低 | 保持 `__Host-token` 名称和属性不变 |
| 测试大面积失效 | 中 | Phase 0 先补测试，每阶段重写对应测试 |
| `OAuth2PasswordRequestForm` 契约差异 | 中 | 前端登录改 `application/x-www-form-urlencoded` |
| Alembic 与 One-shot 规则张力 | 中 | Alembic 只管 DDL，backfill 走一次性脚本，补充 AGENTS.md 规则 |

## 12. 分阶段交付

| 阶段 | 工作量 | 交付内容 |
|---|---|---|
| Phase 0 基线锁定 | 0.5 天 | 补全现有认证测试，录制契约快照 |
| Phase 1 ORM + 迁移 | 2 天 | SQLAlchemy + Alembic + users 表迁移 + backfill 脚本 |
| Phase 2 FastAPI Users 核心 | 3 天 | UserManager + InnovOSJWTStrategy + 路由替换 + 依赖统一 |
| Phase 3 增强 + 前端 | 2 天 | verify/reset 路由 + 邮件服务 + 前端适配 |
| Phase 4 清理固化 | 1 天 | 删旧实现 + 更新文档 + 覆盖率门禁 |
| **合计** | **8.5 天** | |
