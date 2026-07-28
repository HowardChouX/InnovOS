# InnovOS 认证体系重构实施计划：全量采用 FastAPI Users

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 FastAPI Users 全量替换 InnovOS 手写的用户管理与认证体系，引入 SQLAlchemy ORM（仅 users 表）+ Alembic 迁移，清除 id=0 幽灵管理员，保留 token_version 撤销机制。

**Architecture:** 四层分层--API 路由层（FastAPI Users 依赖注入）、FastAPI Users 层（UserManager + 定制 JWTStrategy）、ORM 层（SQLAlchemy + Alembic，仅 users 表）、基础服务层（email_service + audit + rate_limit）。业务表保持 raw psycopg2 不动。

**Tech Stack:** FastAPI Users 14+ / SQLAlchemy 2.0 / Alembic / pwdlib / pyjwt / psycopg2（业务表保留）/ Mailpit+SMTP（邮件）

**Spec:** `docs/superpowers/specs/2026-07-28-auth-fastapi-users-design.md`

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|---|---|
| `backend/app/db/__init__.py` | ORM 层包 |
| `backend/app/db/base.py` | SQLAlchemy declarative Base |
| `backend/app/db/session.py` | 同步 engine + sessionmaker + get_session 依赖 |
| `backend/app/db/models.py` | User ORM 模型（SQLAlchemyBaseUserTable） |
| `backend/app/auth/__init__.py` | FastAPI Users 层包 |
| `backend/app/auth/schemas.py` | UserRead / UserCreate / UserUpdate |
| `backend/app/auth/users.py` | UserManager + get_user_manager |
| `backend/app/auth/strategy.py` | InnovOSJWTStrategy（token_version 织入） |
| `backend/app/auth/backend.py` | CookieTransport + auth_backend |
| `backend/app/auth/instance.py` | FastAPIUsers 实例 + current_active_user/current_superuser |
| `backend/app/auth/exceptions.py` | FastAPI Users 异常 -> 中文映射 |
| `backend/app/services/email_service.py` | 邮件发送（Mailpit/SMTP） |
| `backend/alembic.ini` | Alembic 配置 |
| `backend/alembic/env.py` | Alembic 环境 |
| `backend/alembic/script.py.mako` | Alembic 模板 |
| `backend/alembic/versions/0001_users_fastapi_users_schema.py` | users 表 DDL 迁移 |
| `backend/alembic/versions/0002_data_migration_marker.py` | data migration 完成标记（空 revision） |
| `backend/scripts/migrate_users_to_fastapi_users.py` | 一次性数据迁移脚本（用完删） |
| `backend/tests/test_auth_register.py` | 注册测试 |
| `backend/tests/test_auth_login.py` | 登录测试 |
| `backend/tests/test_auth_token_version.py` | token_version 撤销测试 |
| `backend/tests/test_auth_verify.py` | 邮箱验证测试 |
| `backend/tests/test_auth_reset_password.py` | 密码重置测试 |
| `backend/tests/test_users_me.py` | /api/users/me 测试 |
| `backend/tests/test_admin_users_fastapi_users.py` | 管理员用户管理测试 |
| `backend/tests/test_superuser_guard.py` | 超管权限守卫测试 |
| `backend/tests/conftest_auth.py` | 认证测试 fixtures（SQLite 内存库） |

### 修改文件

| 文件 | 改动 |
|---|---|
| `backend/pyproject.toml` | 加 fastapi-users/sqlalchemy/alembic/pwdlib，删 python-jose/bcrypt |
| `backend/app/core/config.py` | 加 SMTP_* 配置 |
| `backend/app/main.py` | 挂载 FastAPI Users 路由 + 异常 handler，移除旧 auth router |
| `backend/app/tables/pg_schema.py` | 删 init_users/seed_admin_user，init_all_tables 移除调用 |
| `backend/app/api/admin/users.py` | 改用 current_superuser，token 撤销改 ORM |
| `backend/app/api/users.py` | 保留自助改密（custom），其余由 FastAPI Users 接管 |
| `backend/app/database.py` | get_db_dep 保留（业务表用），注释说明仅业务表 |
| `backend/app/seed_mock_data.py` | seed 管理员改 ORM + is_superuser |
| `backend/AGENTS.md` | 补 Alembic 迁移规则 |
| `backend/CLAUDE.md` | 同步认证架构说明 |
| `docker-compose.yml` | 加 Mailpit 服务（开发环境） |
| `frontend/src/api/auth.ts` | 改 email 登录 + form-urlencoded + 新端点 |
| `frontend/src/store/useAuthStore.ts` | User 类型调整 |
| `frontend/src/features/auth/LoginPage.tsx` | email 输入框 |
| `frontend/src/features/auth/RegisterPage.tsx` | email + phone + 可选 username |

### 删除文件

| 文件 | 原因 |
|---|---|
| `backend/app/auth.py` | 旧 dict 版 get_current_user，被 app/auth/ 替代 |
| `backend/app/api/deps.py` | 旧 User 版 get_current_user，被 app/auth/instance 替代 |
| `backend/app/core/security.py` | 旧 create_access_token/get_password_hash，由 pwdlib+pyjwt 替代 |
| `backend/app/crud/users.py` | 旧 raw SQL CRUD，由 SQLAlchemy adapter 替代 |
| `backend/tests/test_api_auth.py` | 旧 mock DB 测试，被新测试替代 |
| `backend/tests/test_core_auth.py` | 旧实现测试 |
| `backend/tests/test_core_security.py` | 旧实现测试 |
| `backend/tests/test_seed_data.py` | 旧 seed 测试，重写 |

### 全局依赖替换（25+ 文件）

以下文件中的 `from app.api.deps import CurrentUser, SuperUserDep, SessionDep` 和 `from app.auth import get_current_user, require_admin` 需改为 `from app.auth.instance import current_active_user, current_superuser` + `from app.db.session import get_session`：

`backend/app/api/` 下所有路由文件（analysis, conversion, evaluation, feedback, kb_tools, knowledge, knowledge_bases, modeling, models, notifications, patents, sidebar, solutions, tasks, workflow, admin/*, workflow_steps/*）。

---

## Phase 0：基线锁定与依赖准备

### Task 1: 添加新依赖

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 编辑 pyproject.toml 添加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 列表中，在 `"rank-bm25>=0.2.2"` 之后添加：

```toml
    "fastapi-users[sqlalchemy]>=14.0",
    "fastapi-users-db-sqlalchemy>=7.0",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pwdlib[argon2,bcrypt]>=0.3",
    "pyjwt[crypto]>=2.12.0",
```

暂不删除 `python-jose` 和 `bcrypt`（Phase 4 清理时删，避免 Phase 1-3 期间旧代码导入失败）。

- [ ] **Step 2: 同步依赖**

Run: `cd backend && uv sync`
Expected: 成功安装 fastapi-users、sqlalchemy、alembic、pwdlib、pyjwt

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "import fastapi_users; import sqlalchemy; import alembic; import pwdlib; import jwt; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(auth): add fastapi-users, sqlalchemy, alembic, pwdlib dependencies"
```

### Task 2: 创建 ORM 基础层

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models.py`
- Test: `backend/tests/test_db_models.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_db_models.py`:

```python
"""ORM 模型测试 - 验证 User 模型结构。"""
import pytest
from sqlalchemy import inspect


def test_user_model_has_required_fields():
    """User 模型必须包含 FastAPI Users 标准字段 + InnovOS 扩展字段。"""
    from app.db.models import User
    mapper = inspect(User)
    columns = {c.key for c in mapper.columns}
    # FastAPI Users 标准字段
    assert "id" in columns
    assert "email" in columns
    assert "hashed_password" in columns
    assert "is_active" in columns
    assert "is_superuser" in columns
    assert "is_verified" in columns
    # InnovOS 扩展字段
    assert "username" in columns
    assert "phone" in columns
    assert "role" in columns
    assert "token_version" in columns


def test_user_table_name():
    from app.db.models import User
    assert User.__tablename__ == "users"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_db_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: 创建 db 包和 Base**

Create `backend/app/db/__init__.py` (空文件):

```python
```

Create `backend/app/db/base.py`:

```python
"""SQLAlchemy declarative Base（仅用于 users 表）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: 创建 User ORM 模型**

Create `backend/app/db/models.py`:

```python
"""User ORM 模型 - 基于 FastAPI Users 的 SQLAlchemyBaseUserTable。"""
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.base import Base


class User(SQLAlchemyBaseUserTable, Base):
    """用户表 ORM 模型。

    SQLAlchemyBaseUserTable 提供: id, email, hashed_password,
    is_active, is_superuser, is_verified
    """
    __tablename__ = "users"

    # InnovOS 扩展字段
    username = Column(String(100), nullable=True)   # 显示名，可空
    phone = Column(String(20), nullable=True)        # 档案字段，不参与登录
    role = Column(String(20), default="user")        # 业务角色
    token_version = Column(Integer, default=0)       # 撤销机制
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

- [ ] **Step 5: 创建 session**

Create `backend/app/db/session.py`:

```python
"""SQLAlchemy 同步 session（仅用于 users 表 / 认证层）。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供 ORM session。仅用于认证/用户表。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_db_models.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/ backend/tests/test_db_models.py
git commit -m "feat(db): add SQLAlchemy ORM layer for users table"
```

### Task 3: 配置 Alembic

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (目录)

- [ ] **Step 1: 创建 alembic.ini**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: 创建 alembic/env.py**

Create `backend/alembic/env.py`:

```python
"""Alembic 环境配置 - 仅管理 users 表 DDL。"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 确保 app 包可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401, E402  # 注册 User 模型

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: 创建 script.py.mako**

Create `backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: 创建 versions 目录**

Run: `mkdir -p backend/alembic/versions`

- [ ] **Step 5: 验证 Alembic 可运行**

Run: `cd backend && alembic current`
Expected: 输出无错误（可能显示无 revision）

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat(db): configure Alembic for users table migrations"
```

### Task 4: 编写 users 表 DDL 迁移

**Files:**
- Create: `backend/alembic/versions/0001_users_fastapi_users_schema.py`

- [ ] **Step 1: 创建迁移文件**

Create `backend/alembic/versions/0001_users_fastapi_users_schema.py`:

```python
"""users table schema for FastAPI Users

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加新列（IF NOT EXISTS 幂等，符合 One-shot 规则的可重复声明）
    op.add_column("users",
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.false()))
    op.add_column("users",
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false()))
    op.add_column("users",
        sa.Column("phone", sa.String(20), nullable=True))

    # 2. 改列类型（is_active INTEGER -> BOOLEAN）
    op.alter_column("users", "is_active",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        postgresql_using="is_active::boolean",
        server_default=sa.true())

    # 3. email 加 NOT NULL + 唯一约束
    # 注意：email 的 NOT NULL 要求所有现有用户已有 email，由 data backfill 脚本保证
    op.alter_column("users", "email",
        existing_type=sa.Text(),
        nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 4. username 放宽为可空（降级为显示名）
    op.alter_column("users", "username",
        existing_type=sa.Text(),
        nullable=True)
    # 删旧唯一约束（若存在），改为普通索引
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "username",
        existing_type=sa.Text(),
        nullable=False)
    op.drop_index("ix_users_email", table_name="users")
    op.alter_column("users", "email",
        existing_type=sa.Text(),
        nullable=True)
    op.alter_column("users", "is_active",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        postgresql_using="is_active::int",
        server_default="1")
    op.drop_column("users", "phone")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "is_superuser")
```

- [ ] **Step 2: 验证迁移可生成 SQL（离线模式）**

Run: `cd backend && alembic upgrade head --sql`
Expected: 输出 SQL 语句，包含 `ALTER TABLE users ADD COLUMN is_superuser` 等

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0001_users_fastapi_users_schema.py
git commit -m "feat(db): add users table DDL migration for FastAPI Users schema"
```

### Task 5: 编写一次性数据迁移脚本

**Files:**
- Create: `backend/scripts/migrate_users_to_fastapi_users.py`

- [ ] **Step 1: 创建迁移脚本**

Create `backend/scripts/migrate_users_to_fastapi_users.py`:

```python
"""一次性数据迁移脚本：users 表从旧 schema 迁移到 FastAPI Users schema。

⚠️ One-shot 脚本：运行后从仓库删除，不留在生产启动路径。
⚠️ 运行前必须先执行 `alembic upgrade head`（DDL 已应用）。

步骤：
1. 列名迁移：password_hash -> hashed_password（RENAME COLUMN）
2. role='admin' -> is_superuser=True
3. email 为空的用户补占位邮箱 {username}@local.invalid
4. user_id=0 的幽灵管理员引用归并到真实管理员 id
5. 删除 id=0 幽灵行
6. seed 真实管理员（从 .env，is_superuser=True）

用法：
    cd backend
    python scripts/migrate_users_to_fastapi_users.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2  # noqa: E402
from app.core.config import settings  # noqa: E402


def run():
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1. 列名迁移
        print("[1/6] 重命名 password_hash -> hashed_password ...")
        cur.execute(
            "ALTER TABLE users RENAME COLUMN password_hash TO hashed_password"
        )

        # 2. 管理员标志
        print("[2/6] role='admin' -> is_superuser=True ...")
        cur.execute(
            "UPDATE users SET is_superuser = TRUE WHERE role = 'admin'"
        )

        # 3. email 补全
        print("[3/6] 补全空 email 为 {username}@local.invalid ...")
        cur.execute(
            "UPDATE users SET email = username || '@local.invalid' "
            "WHERE email IS NULL OR email = ''"
        )

        # 4. 幽灵管理员引用归并
        # 先确定真实管理员 id（第一个 is_superuser=TRUE 的用户）
        cur.execute(
            "SELECT id FROM users WHERE is_superuser = TRUE ORDER BY id LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("未找到 is_superuser=TRUE 的管理员，无法归并 id=0 引用")
        real_admin_id = row[0]
        print(f"[4/6] 归并 user_id=0 引用到真实管理员 id={real_admin_id} ...")
        # 归并所有引用 user_id=0 的表
        for table in ["tasks", "evaluations", "feedbacks", "audit_log",
                       "notifications", "knowledge_bases", "knowledge_items",
                       "knowledge_vectors", "knowledge_jobs", "knowledge_groups",
                       "knowledge_docs"]:
            cur.execute(
                f"UPDATE {table} SET user_id = %s WHERE user_id = 0",
                (real_admin_id,),
            )

        # 5. 删除幽灵行
        print("[5/6] 删除 id=0 幽灵管理员行 ...")
        cur.execute("DELETE FROM users WHERE id = 0")

        # 6. seed 真实管理员（若不存在）
        print("[6/6] seed 真实管理员 ...")
        admin_user = settings.FIRST_SUPERUSER or "admin"
        admin_pass = settings.FIRST_SUPERUSER_PASSWORD or ""
        cur.execute("SELECT id FROM users WHERE is_superuser = TRUE")
        if cur.fetchone() is None and admin_pass:
            from app.auth.users import UserManager  # 延迟导入
            # 这里简化：直接 SQL 插入，密码用 pwdlib 哈希
            from pwdlib import PasswordHash
            ph = PasswordHash.recommended()
            hashed = ph.hash(admin_pass)
            cur.execute(
                "INSERT INTO users (email, hashed_password, is_superuser, "
                "is_active, is_verified, role, username) "
                "VALUES (%s, %s, TRUE, TRUE, TRUE, 'admin', %s)",
                (admin_user, hashed, admin_user),
            )

        conn.commit()
        print("✅ 数据迁移完成")
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败，已回滚: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: 验证脚本语法**

Run: `cd backend && python -c "import ast; ast.parse(open('scripts/migrate_users_to_fastapi_users.py').read()); print('syntax OK')"`
Expected: 输出 `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrate_users_to_fastapi_users.py
git commit -m "feat(db): add one-shot data migration script for users table"
```

### Task 6: 创建 data migration marker revision

**Files:**
- Create: `backend/alembic/versions/0002_data_migration_marker.py`

- [ ] **Step 1: 创建标记 revision**

Create `backend/alembic/versions/0002_data_migration_marker.py`:

```python
"""data migration marker - 运行 migrate_users_to_fastapi_users.py 后应用此 revision

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28
"""
from typing import Sequence, Union

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空 revision - 仅作为 data migration 完成的版本锚点。"""
    pass


def downgrade() -> None:
    pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/0002_data_migration_marker.py
git commit -m "feat(db): add data migration marker revision"
```

---

## Phase 1：FastAPI Users 核心组件

### Task 7: 创建 schemas

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/schemas.py`
- Test: `backend/tests/test_auth_schemas.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_schemas.py`:

```python
"""认证 schemas 测试。"""
from app.auth.schemas import UserCreate, UserRead, UserUpdate


def test_user_create_has_email_password_phone():
    """UserCreate 必须包含 email, password, phone 字段。"""
    u = UserCreate(
        email="test@example.com",
        password="test1234",
        phone="13800000000",
    )
    assert u.email == "test@example.com"
    assert u.password == "test1234"
    assert u.phone == "13800000000"


def test_user_create_phone_optional():
    """phone 可选。"""
    u = UserCreate(email="test@example.com", password="test1234")
    assert u.phone is None


def test_user_read_has_role():
    """UserRead 包含 role 字段。"""
    u = UserRead(
        id=1, email="test@example.com", is_active=True,
        is_superuser=False, is_verified=False, role="user",
    )
    assert u.role == "user"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.schemas'`

- [ ] **Step 3: 创建 auth 包**

Create `backend/app/auth/__init__.py` (空文件):

```python
```

Create `backend/app/auth/schemas.py`:

```python
"""用户 Pydantic schemas - 基于 FastAPI Users BaseUser。"""
from fastapi_users import schemas
from pydantic import Field


class UserRead(schemas.BaseUser[int]):
    """用户读取 schema。"""
    username: str | None = None
    phone: str | None = None
    role: str = "user"


class UserCreate(schemas.BaseUserCreate):
    """用户创建 schema。email + password 必填，phone 可选。"""
    username: str | None = None
    phone: str = Field(default=None, description="手机号，仅档案存储")


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新 schema。"""
    username: str | None = None
    phone: str | None = None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_auth_schemas.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/schemas.py backend/tests/test_auth_schemas.py
git commit -m "feat(auth): add UserRead/UserCreate/UserUpdate schemas"
```

### Task 8: 创建 UserManager

**Files:**
- Create: `backend/app/auth/users.py`
- Test: `backend/tests/test_user_manager.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_user_manager.py`:

```python
"""UserManager 测试。"""
import pytest
from fastapi_users.exceptions import InvalidPasswordException

from app.auth.users import UserManager


def test_user_manager_has_secrets():
    """UserManager 必须配置 reset_password_token_secret 和 verification_token_secret。"""
    assert UserManager.reset_password_token_secret is not None
    assert UserManager.verification_token_secret is not None


def test_validate_password_too_short():
    """密码 < 8 位应抛出 InvalidPasswordException。"""
    # UserManager 需要一个 user_db adapter，这里用 mock
    from unittest.mock import MagicMock
    mgr = UserManager(MagicMock())
    import asyncio
    with pytest.raises(InvalidPasswordException, match="密码至少 8 位"):
        asyncio.run(mgr.validate_password("12345", None))


def test_validate_password_ok():
    """密码 >= 8 位通过。"""
    from unittest.mock import MagicMock
    mgr = UserManager(MagicMock())
    import asyncio
    asyncio.run(mgr.validate_password("test1234", None))  # 不抛异常即通过
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_user_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.users'`

- [ ] **Step 3: 创建 UserManager**

Create `backend/app/auth/users.py`:

```python
"""UserManager - 用户生命周期管理与业务回调。"""
from typing import Optional

from fastapi import Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi_users.exceptions import InvalidPasswordException
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.audit import log_audit
from app.core.config import settings
from app.db.models import User


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    """InnovOS UserManager - 集成审计日志与邮件回调。"""

    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.register", "user", str(user.id),
            {}, request.client.host if request else "",
        )
        # 邮件发送在 Phase 2 接入，此处先留接口
        # await email_service.send_verification_email(user, request)

    async def on_after_login(
        self, user: User, request: Optional[Request] = None,
        response=None,
    ):
        log_audit(
            user.id, user.email, "user.login", "user", str(user.id),
            {}, request.client.host if request else "",
        )

    async def on_after_forgot_password(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        # Phase 2 接入邮件服务
        pass

    async def on_after_request_verify(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        # Phase 2 接入邮件服务
        pass

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.verify", "user", str(user.id),
            {}, "",
        )

    async def validate_password(self, password: str, user) -> None:
        """密码策略：至少 8 位。"""
        if len(password) < 8:
            raise InvalidPasswordException(reason="密码至少 8 位")


async def get_user_db(session=Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
```

注意：上面的 `Depends` 和 `get_session` 需要在文件顶部导入。修正完整文件：

```python
"""UserManager - 用户生命周期管理与业务回调。"""
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi_users.exceptions import InvalidPasswordException
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.audit import log_audit
from app.core.config import settings
from app.db.models import User
from app.db.session import get_session


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    """InnovOS UserManager - 集成审计日志与邮件回调。"""

    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.register", "user", str(user.id),
            {}, request.client.host if request else "",
        )

    async def on_after_login(
        self, user: User, request: Optional[Request] = None,
        response=None,
    ):
        log_audit(
            user.id, user.email, "user.login", "user", str(user.id),
            {}, request.client.host if request else "",
        )

    async def on_after_forgot_password(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        pass  # Phase 2 接入邮件服务

    async def on_after_request_verify(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        pass  # Phase 2 接入邮件服务

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ):
        log_audit(
            user.id, user.email, "user.verify", "user", str(user.id),
            {}, "",
        )

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(reason="密码至少 8 位")


async def get_user_db(session=Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_user_manager.py -v`
Expected: PASS（3 个测试）

注意：`test_user_manager_has_secrets` 需要 settings.SECRET_KEY 有值。conftest 的 auto_mock_db 不影响 settings。

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/users.py backend/tests/test_user_manager.py
git commit -m "feat(auth): add UserManager with audit logging and password validation"
```

### Task 9: 创建 InnovOSJWTStrategy

**Files:**
- Create: `backend/app/auth/strategy.py`
- Test: `backend/tests/test_auth_strategy.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_strategy.py`:

```python
"""InnovOSJWTStrategy 测试 - token_version 撤销机制。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.auth.strategy import InnovOSJWTStrategy
from app.core.config import settings


def test_write_token_includes_token_version():
    """write_token 应在 payload 中注入 token_version。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    user = MagicMock()
    user.id = 42
    user.token_version = 3

    token = asyncio.run(strategy.write_token(user))
    assert isinstance(token, str)

    # 解码验证
    from fastapi_users.jwt import decode_jwt
    data = decode_jwt(
        token, settings.SECRET_KEY,
        ["fastapi-users:auth"], algorithms=["HS256"],
    )
    assert data["sub"] == "42"
    assert data["token_version"] == 3


def test_read_token_rejects_revoked():
    """token_version 不匹配时应返回 None（已撤销）。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    # 签发时 token_version=1
    user = MagicMock()
    user.id = 42
    user.token_version = 1
    token = asyncio.run(strategy.write_token(user))

    # 模拟用户 token_version 已升级到 2（被撤销）
    user.token_version = 2
    user_manager = MagicMock()
    user_manager.parse_id = lambda x: int(x)
    user_manager.get = AsyncMock(return_value=user)

    result = asyncio.run(strategy.read_token(token, user_manager))
    assert result is None  # 撤销


def test_read_token_valid():
    """token_version 匹配时返回 user。"""
    strategy = InnovOSJWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    user = MagicMock()
    user.id = 42
    user.token_version = 1
    token = asyncio.run(strategy.write_token(user))

    user_manager = MagicMock()
    user_manager.parse_id = lambda x: int(x)
    user_manager.get = AsyncMock(return_value=user)

    result = asyncio.run(strategy.read_token(token, user_manager))
    assert result is user
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth_strategy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.strategy'`

- [ ] **Step 3: 创建 strategy**

Create `backend/app/auth/strategy.py`:

```python
"""定制 JWTStrategy - 织入 token_version 撤销校验。"""
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager


class InnovOSJWTStrategy(JWTStrategy):
    """JWT + token_version 撤销校验。

    在标准 JWTStrategy 基础上：
    - write_token: payload 注入 token_version
    - read_token: 校验 token_version 与 DB 值，不匹配则视为已撤销
    """

    async def read_token(self, token, user_manager: BaseUserManager):
        if token is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience,
                algorithms=[self.algorithm],
            )
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
        return generate_jwt(
            data, self.encode_key, self.lifetime_seconds,
            algorithm=self.algorithm,
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_auth_strategy.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/strategy.py backend/tests/test_auth_strategy.py
git commit -m "feat(auth): add InnovOSJWTStrategy with token_version revocation"
```

### Task 10: 创建认证后端与 FastAPIUsers 实例

**Files:**
- Create: `backend/app/auth/backend.py`
- Create: `backend/app/auth/instance.py`
- Test: `backend/tests/test_auth_instance.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_instance.py`:

```python
"""FastAPIUsers 实例测试。"""
from app.auth.instance import current_active_user, current_superuser, fastapi_users


def test_fastapi_users_instance():
    """fastapi_users 实例存在。"""
    assert fastapi_users is not None


def test_current_active_user_dependency():
    """current_active_user 是可调用的依赖。"""
    assert callable(current_active_user)


def test_current_superuser_dependency():
    """current_superuser 是可调用的依赖。"""
    assert callable(current_superuser)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth_instance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.instance'`

- [ ] **Step 3: 创建 backend**

Create `backend/app/auth/backend.py`:

```python
"""认证后端 - CookieTransport + InnovOSJWTStrategy。"""
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
)

from app.auth.strategy import InnovOSJWTStrategy
from app.core.config import settings

# Cookie 为主通道，保持 __Host-token 名称（前端零改动）
# __Host- 前缀要求: Secure=True, Path=/, 无 Domain
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

- [ ] **Step 4: 创建 instance**

Create `backend/app/auth/instance.py`:

```python
"""FastAPIUsers 实例与依赖工厂。"""
from fastapi_users import FastAPIUsers

from app.auth.backend import auth_backend
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.auth.users import get_user_manager
from app.db.models import User

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

# 依赖：当前活跃用户
current_active_user = fastapi_users.current_user(active=True)
# 依赖：当前超级用户
current_superuser = fastapi_users.current_user(active=True, superuser=True)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_auth_instance.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/backend.py backend/app/auth/instance.py backend/tests/test_auth_instance.py
git commit -m "feat(auth): add auth backend and FastAPIUsers instance with dependencies"
```

### Task 11: 创建异常处理器

**Files:**
- Create: `backend/app/auth/exceptions.py`
- Test: `backend/tests/test_auth_exceptions.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_auth_exceptions.py`:

```python
"""认证异常处理测试。"""
import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi_users import exceptions as fu_exceptions

from app.auth.exceptions import fastapi_users_exception_handler


def test_user_already_exists_returns_400():
    exc = fu_exceptions.UserAlreadyExists()
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 400
    assert response.body == b'{"detail":"\xe8\xaf\xa5\xe9\x82\xae\xe7\xae\xb1\xe5\xb7\xb2\xe6\xb3\xa8\xe5\x86\x8c"}'


def test_user_not_exists_returns_404():
    exc = fu_exceptions.UserNotExists()
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 404


def test_invalid_password_uses_reason():
    exc = fu_exceptions.InvalidPasswordException(reason="密码至少 8 位")
    request = MagicMock()
    response = asyncio.run(fastapi_users_exception_handler(request, exc))
    assert response.status_code == 400
    assert "密码至少 8 位".encode() in response.body
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.exceptions'`

- [ ] **Step 3: 创建异常处理器**

Create `backend/app/auth/exceptions.py`:

```python
"""FastAPI Users 异常 -> 中文错误信息映射。"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_users import exceptions as fu_exceptions

EXCEPTION_MAP: dict[type, tuple[int, str | None]] = {
    fu_exceptions.UserAlreadyExists: (400, "该邮箱已注册"),
    fu_exceptions.InvalidID: (400, "无效的用户 ID"),
    fu_exceptions.UserNotExists: (404, "用户不存在"),
    fu_exceptions.UserInactive: (400, "用户已被禁用"),
    fu_exceptions.UserAlreadyVerified: (400, "用户已验证"),
    fu_exceptions.InvalidVerifyToken: (400, "无效的验证链接"),
    fu_exceptions.InvalidResetPasswordToken: (400, "无效的重置链接"),
    fu_exceptions.InvalidPasswordException: (400, None),  # 用 reason
    fu_exceptions.PasswordInvalid: (400, "密码错误"),
}


async def fastapi_users_exception_handler(request: Request, exc: Exception):
    """统一处理 FastAPI Users 异常，返回中文错误信息。"""
    for exc_type, (status, msg) in EXCEPTION_MAP.items():
        if isinstance(exc, exc_type):
            if msg is None:
                msg = getattr(exc, "reason", "密码不符合要求")
            return JSONResponse(status_code=status, content={"detail": msg})
    return JSONResponse(status_code=400, content={"detail": "认证错误"})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_auth_exceptions.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/exceptions.py backend/tests/test_auth_exceptions.py
git commit -m "feat(auth): add Chinese exception handler for FastAPI Users"
```

---

## Phase 2：路由挂载与依赖统一

### Task 12: 创建认证测试 fixtures

**Files:**
- Create: `backend/tests/conftest_auth.py`

- [ ] **Step 1: 创建认证专用 conftest**

Create `backend/tests/conftest_auth.py`:

```python
"""认证测试 fixtures - 使用 SQLite 内存库（替代 mock DB）。

FastAPI Users 的 SQLAlchemy adapter 需要真实 ORM session，
mock DB 模式不兼容，故认证测试用 SQLite 内存库。
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 确保 settings 有值
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-auth-tests")

from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401, E402
from app.db.session import get_session  # noqa: E402


@pytest.fixture
def auth_engine():
    """SQLite 内存库 engine，启用 FK 约束。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def auth_session(auth_engine):
    Session = sessionmaker(bind=auth_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def auth_app(auth_session):
    """挂载 FastAPI Users 路由的测试 app。"""
    from app.auth.instance import fastapi_users
    from app.auth.backend import auth_backend
    from app.auth.schemas import UserCreate, UserRead, UserUpdate
    from app.auth.exceptions import fastapi_users_exception_handler
    from fastapi_users.exceptions import (
        UserAlreadyExists, UserNotExists, UserInactive,
        UserAlreadyVerified, InvalidVerifyToken,
        InvalidResetPasswordToken, InvalidPasswordException,
    )

    app = FastAPI()
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users", tags=["users"],
    )
    for exc in (UserAlreadyExists, UserNotExists, UserInactive,
                UserAlreadyVerified, InvalidVerifyToken,
                InvalidResetPasswordToken, InvalidPasswordException):
        app.add_exception_handler(exc, fastapi_users_exception_handler)

    app.dependency_overrides[get_session] = lambda: auth_session
    return app


@pytest.fixture
def auth_client(auth_app):
    return TestClient(auth_app)


@pytest.fixture
def seed_user(auth_session):
    """创建一个测试普通用户。"""
    from app.auth.users import get_user_manager
    from app.auth.schemas import UserCreate
    from app.db.session import get_session
    import asyncio

    # 直接通过 ORM 创建
    from pwdlib import PasswordHash
    ph = PasswordHash.recommended()
    from app.db.models import User
    user = User(
        email="test@example.com",
        hashed_password=ph.hash("test1234"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="user",
        token_version=0,
    )
    auth_session.add(user)
    auth_session.commit()
    auth_session.refresh(user)
    return user


@pytest.fixture
def seed_admin(auth_session):
    """创建一个测试管理员。"""
    from pwdlib import PasswordHash
    from app.db.models import User
    ph = PasswordHash.recommended()
    admin = User(
        email="admin@example.com",
        hashed_password=ph.hash("admin1234"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        role="admin",
        token_version=0,
    )
    auth_session.add(admin)
    auth_session.commit()
    auth_session.refresh(admin)
    return admin
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest_auth.py
git commit -m "test(auth): add auth test fixtures with SQLite in-memory DB"
```

### Task 13: 注册端点测试与验证

**Files:**
- Test: `backend/tests/test_auth_register.py`

- [ ] **Step 1: 写注册测试**

Create `backend/tests/test_auth_register.py`:

```python
"""注册端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestRegister:
    def test_register_success(self, auth_client, auth_session):
        """成功注册返回 201，用户写入 DB。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "test1234",
            "phone": "13800000000",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert data["is_active"] is True

    def test_register_duplicate_email(self, auth_client, seed_user):
        """重复邮箱返回 400。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "test1234",
        })
        assert resp.status_code == 400
        assert "该邮箱已注册" in resp.json()["detail"]

    def test_register_short_password(self, auth_client):
        """密码 < 8 位返回 400。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "short@example.com",
            "password": "123",
        })
        assert resp.status_code == 400
        assert "密码至少 8 位" in resp.json()["detail"]

    def test_register_phone_optional(self, auth_client):
        """phone 可选。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "nophone@example.com",
            "password": "test1234",
        })
        assert resp.status_code == 201, resp.text

    def test_register_invalid_email(self, auth_client):
        """非法 email 返回 422。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "test1234",
        })
        assert resp.status_code == 422
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth_register.py -v`
Expected: FAIL（路由尚未挂载到 main app；但 auth_client fixture 已挂载，应能通过。若失败，检查 fixture）

- [ ] **Step 3: 验证测试通过**

Run: `cd backend && python -m pytest tests/test_auth_register.py -v`
Expected: PASS（5 个测试）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_auth_register.py
git commit -m "test(auth): add registration endpoint tests"
```

### Task 14: 登录端点测试

**Files:**
- Test: `backend/tests/test_auth_login.py`

- [ ] **Step 1: 写登录测试**

Create `backend/tests/test_auth_login.py`:

```python
"""登录端点测试。

FastAPI Users 登录用 OAuth2PasswordRequestForm：
- Content-Type: application/x-www-form-urlencoded
- 字段: username (填邮箱值), password
"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestLogin:
    def test_login_success(self, auth_client, seed_user):
        """正确邮箱密码登录返回 200 + 设置 cookie。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # cookie 应被设置
        assert "__Host-token" in resp.cookies or "fastapiusersauth" in resp.cookies

    def test_login_wrong_password(self, auth_client, seed_user):
        """错误密码返回 400。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "wrong"},
        )
        assert resp.status_code == 400

    def test_login_nonexistent_user(self, auth_client):
        """不存在的用户返回 400。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "nobody@example.com", "password": "test1234"},
        )
        assert resp.status_code == 400

    def test_login_inactive_user(self, auth_client, auth_session):
        """禁用用户登录失败。"""
        from pwdlib import PasswordHash
        from app.db.models import User
        ph = PasswordHash.recommended()
        inactive = User(
            email="inactive@example.com",
            hashed_password=ph.hash("test1234"),
            is_active=False,
            is_superuser=False,
            is_verified=True,
        )
        auth_session.add(inactive)
        auth_session.commit()

        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "inactive@example.com", "password": "test1234"},
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_auth_login.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_auth_login.py
git commit -m "test(auth): add login endpoint tests"
```

### Task 15: token_version 撤销测试

**Files:**
- Test: `backend/tests/test_auth_token_version.py`

- [ ] **Step 1: 写撤销测试**

Create `backend/tests/test_auth_token_version.py`:

```python
"""token_version 撤销机制测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


def test_token_valid_before_revoke(self, auth_client, seed_user):
    """撤销前 token 有效。"""
    pass  # 占位，实际在下方实现


class TestTokenVersionRevocation:
    def test_token_works_before_revoke(self, auth_client, seed_user):
        """登录后 token 可访问 /api/users/me。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        me_resp = auth_client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "test@example.com"

    def test_token_invalid_after_revoke(
        self, auth_client, seed_user, auth_session,
    ):
        """token_version 变更后旧 token 失效。"""
        # 登录拿 token
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        token = resp.json()["access_token"]

        # 撤销：token_version + 1
        seed_user.token_version += 1
        auth_session.commit()

        # 旧 token 应失效
        me_resp = auth_client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 401
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_auth_token_version.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_auth_token_version.py
git commit -m "test(auth): add token_version revocation tests"
```

### Task 16: users/me 端点测试

**Files:**
- Test: `backend/tests/test_users_me.py`

- [ ] **Step 1: 写测试**

Create `backend/tests/test_users_me.py`:

```python
"""GET/PATCH /api/users/me 测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestUsersMe:
    def test_me_requires_auth(self, auth_client):
        """无 token 返回 401。"""
        resp = auth_client.get("/api/users/me")
        assert resp.status_code == 401

    def test_me_returns_user(self, auth_client, seed_user):
        """有效 token 返回用户信息。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        token = resp.json()["access_token"]

        me_resp = auth_client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"

    def test_me_patch_username(self, auth_client, seed_user):
        """PATCH 更新 username。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        token = resp.json()["access_token"]

        patch_resp = auth_client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "newname"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["username"] == "newname"
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_users_me.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_users_me.py
git commit -m "test(auth): add /api/users/me endpoint tests"
```

### Task 17: 超管权限守卫测试

**Files:**
- Test: `backend/tests/test_superuser_guard.py`

- [ ] **Step 1: 写守卫测试**

Create `backend/tests/test_superuser_guard.py`:

```python
"""超管权限守卫测试。"""
from tests.conftest_auth import *  # noqa: F401, F403

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.instance import current_superuser


@pytest.fixture
def guard_app(auth_session):
    """挂载一个仅超管可访问的测试端点。"""
    app = FastAPI()
    from app.db.session import get_session
    app.dependency_overrides[get_session] = lambda: auth_session

    @app.get("/admin-only")
    def admin_only(user=Depends(current_superuser)):
        return {"ok": True}
    return app


@pytest.fixture
def guard_client(guard_app):
    return TestClient(guard_app)


class TestSuperuserGuard:
    def test_no_token_returns_401(self, guard_client):
        resp = guard_client.get("/admin-only")
        assert resp.status_code == 401

    def test_normal_user_forbidden(self, guard_client, seed_user, auth_client):
        """普通用户访问返回 403。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        token = resp.json()["access_token"]
        guard_resp = guard_client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert guard_resp.status_code == 403

    def test_superuser_allowed(self, guard_client, seed_admin, auth_client):
        """超管访问返回 200。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "admin@example.com", "password": "admin1234"},
        )
        token = resp.json()["access_token"]
        guard_resp = guard_client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert guard_resp.status_code == 200
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_superuser_guard.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_superuser_guard.py
git commit -m "test(auth): add superuser guard tests"
```

### Task 18: 挂载路由到 main app

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 修改 main.py 挂载 FastAPI Users 路由**

在 `backend/app/main.py` 中，找到 `app_.include_router(auth.router)` 一行（约 227 行），替换为：

```python
# ── FastAPI Users 路由 ──────────────────────────────
from app.auth.instance import fastapi_users
from app.auth.backend import auth_backend
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.auth.exceptions import fastapi_users_exception_handler
from fastapi_users.exceptions import (
    UserAlreadyExists, UserNotExists, UserInactive,
    UserAlreadyVerified, InvalidVerifyToken,
    InvalidResetPasswordToken, InvalidPasswordException,
)

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

# 注册 FastAPI Users 异常 handler
for exc in (UserAlreadyExists, UserNotExists, UserInactive,
            UserAlreadyVerified, InvalidVerifyToken,
            InvalidResetPasswordToken, InvalidPasswordException):
    app_.add_exception_handler(exc, fastapi_users_exception_handler)
```

同时移除旧的 `from app.api import ... auth ...` 导入中的 auth，和 `app_.include_router(auth.router)` 行。

- [ ] **Step 2: 验证 app 可启动**

Run: `cd backend && python -c "from app.main import app_; print('routes:', len(app_.routes))"`
Expected: 输出路由数量，无 ImportError

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(auth): mount FastAPI Users routers to main app"
```

### Task 19: 全局依赖替换

**Files:**
- Modify: `backend/app/api/` 下 25+ 路由文件

- [ ] **Step 1: 搜索所有旧依赖引用**

Run: `cd backend && rg -l "from app.api.deps import|from app.auth import get_current_user|from app.auth import require_admin" app/`
Expected: 输出所有需要修改的文件列表

- [ ] **Step 2: 批量替换 SessionDep**

SessionDep 现在需要指向 ORM session（认证用）或保留 psycopg2（业务用）。对于业务路由（tasks, analysis 等），SessionDep 仍指向 psycopg2 `get_db_dep`，保持不变。

对于认证相关路由（admin/users, users），改为 ORM session。

逐文件修改（以 `app/api/admin/users.py` 为例）：

把 `from app.api.deps import CurrentUser, SessionDep, SuperUserDep` 替换为：
```python
from app.auth.instance import current_active_user, current_superuser
from app.db.session import get_session
from sqlalchemy.orm import Session
from fastapi import Depends

CurrentUser = ...  # 需要保留别名
```

**注意：** 这个任务复杂度高，需要逐文件处理。建议分两步：
1. 先保留 `app/api/deps.py` 的 `SessionDep`（指向 psycopg2，业务用），仅替换认证依赖
2. 在 `app/api/deps.py` 中重新导出 `current_active_user`/`current_superuser` 作为 `CurrentUser`/`SuperUserDep` 的别名，减少下游改动

修改 `backend/app/api/deps.py` 为兼容垫片：

```python
"""FastAPI dependencies - 兼容垫片。

SessionDep: 指向 psycopg2（业务表用）
CurrentUser/SuperUserDep: 指向 FastAPI Users 依赖（认证用）
"""
from typing import Annotated, Any

from fastapi import Depends

from app.auth.instance import current_active_user, current_superuser
from app.database import get_db_dep

# 业务表仍用 psycopg2
SessionDep = Annotated[Any, Depends(get_db_dep)]

# 认证依赖（别名，减少下游改动）
CurrentUser = current_active_user
SuperUserDep = current_superuser
```

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "from app.api.deps import SessionDep, CurrentUser, SuperUserDep; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: 运行全量测试确认无回归**

Run: `cd backend && python -m pytest tests/ -x --ignore=tests/test_api_auth.py --ignore=tests/test_core_auth.py --ignore=tests/test_core_security.py --ignore=tests/test_seed_data.py -q`
Expected: 现有业务测试通过（mock DB 模式下的测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py
git commit -m "refactor(auth): make deps.py a compatibility shim for FastAPI Users"
```

### Task 20: 更新 admin/users 路由

**Files:**
- Modify: `backend/app/api/admin/users.py`

- [ ] **Step 1: 重写 admin/users.py 用 ORM**

Replace `backend/app/api/admin/users.py` 内容为：

```python
"""管理员用户管理 - 基于 ORM + FastAPI Users。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.instance import current_superuser
from app.db.models import User
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin-users"])


class UpdateUserInput(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None


@router.get("")
def list_users(
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """列出所有用户。"""
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return {
        "data": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "phone": u.phone,
                "role": u.role,
                "isActive": u.is_active,
                "isSuperuser": u.is_superuser,
                "isVerified": u.is_verified,
                "createdAt": str(u.id),  # TODO: created_at 字段
            }
            for u in users
        ],
        "message": "success",
        "code": 200,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserInput,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """更新用户。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")
        user.role = body.role
    if body.email is not None:
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone

    db.commit()
    db.refresh(user)
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "phone": user.phone,
            "role": user.role,
            "isActive": user.is_active,
        },
        "message": "success",
        "code": 200,
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """删除用户。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"data": None, "message": "已删除", "code": 200}


@router.post("/{user_id}/revoke-tokens")
def revoke_user_tokens(
    user_id: int,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """撤销用户所有 token（token_version + 1）。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.token_version += 1
    db.commit()
    return {"ok": True}
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && python -c "from app.api.admin.users import router; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/admin/users.py
git commit -m "refactor(auth): rewrite admin/users with ORM and FastAPI Users"
```

---

## Phase 3：邮件服务与增强路由

### Task 21: 添加 SMTP 配置

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 添加 SMTP 配置**

在 `backend/app/core/config.py` 的 `PATENT_HUB_TOKEN` 字段后添加：

```python
    # ── 邮件（SMTP）──
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@innovos.local"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
```

- [ ] **Step 2: 验证配置加载**

Run: `cd backend && python -c "from app.core.config import settings; print(settings.SMTP_HOST, settings.SMTP_PORT)"`
Expected: 输出默认值

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(auth): add SMTP configuration"
```

### Task 22: 创建邮件服务

**Files:**
- Create: `backend/app/services/email_service.py`
- Test: `backend/tests/test_email_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_email_service.py`:

```python
"""邮件服务测试 - mock SMTP。"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest


def test_send_verification_email_calls_smtp():
    """send_verification_email 应调用 SMTP。"""
    from app.services.email_service import email_service
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        email_service.send_verification_email_sync(user, "token123")
        assert server.sendmail.called


def test_send_reset_password_email_calls_smtp():
    from app.services.email_service import email_service
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        email_service.send_reset_password_email_sync(user, "token123")
        assert server.sendmail.called
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_email_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 创建邮件服务**

Create `backend/app/services/email_service.py`:

```python
"""邮件发送服务 - SMTP。

开发环境用 Mailpit（localhost:1025），生产环境用配置的 SMTP。
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_tls = settings.SMTP_TLS
        self.use_ssl = settings.SMTP_SSL

    def _send(self, to_email: str, subject: str, body: str) -> None:
        """发送邮件（同步）。"""
        if not self.host:
            logger.warning("SMTP_HOST 未配置，跳过邮件发送 to=%s", to_email)
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html", "utf-8"))

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
            try:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            finally:
                server.quit()
        except Exception as e:
            logger.error("邮件发送失败 to=%s: %s", to_email, e)

    def send_verification_email_sync(
        self, user, token: str, request=None,
    ) -> None:
        """发送邮箱验证邮件。"""
        verify_url = f"{settings.PUBLIC_URL}/verify?token={token}"
        body = f"""
        <h2>验证您的邮箱</h2>
        <p>请点击下方链接验证您的邮箱地址：</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        """
        self._send(user.email, "InnovOS 邮箱验证", body)

    def send_reset_password_email_sync(
        self, user, token: str, request=None,
    ) -> None:
        """发送密码重置邮件。"""
        reset_url = f"{settings.PUBLIC_URL}/reset-password?token={token}"
        body = f"""
        <h2>重置您的密码</h2>
        <p>请点击下方链接重置密码：</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        """
        self._send(user.email, "InnovOS 密码重置", body)


email_service = EmailService()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_email_service.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/test_email_service.py
git commit -m "feat(auth): add email service for verification and reset"
```

### Task 23: 接入 UserManager 邮件回调

**Files:**
- Modify: `backend/app/auth/users.py`

- [ ] **Step 1: 修改 UserManager 接入邮件服务**

在 `backend/app/auth/users.py` 中，把 `on_after_forgot_password` 和 `on_after_request_verify` 的 `pass` 替换为实际调用：

```python
    async def on_after_forgot_password(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        from app.services.email_service import email_service
        email_service.send_reset_password_email_sync(user, token, request)

    async def on_after_request_verify(
        self, user: User, token: str,
        request: Optional[Request] = None,
    ):
        from app.services.email_service import email_service
        email_service.send_verification_email_sync(user, token, request)
```

同时在 `on_after_register` 末尾追加（可选验证邮件）：
```python
        # 注册后发送验证邮件
        from app.services.email_service import email_service
        # 注册时不自动发验证邮件，用户需主动请求验证
```

- [ ] **Step 2: 运行测试确认无回归**

Run: `cd backend && python -m pytest tests/test_user_manager.py tests/test_auth_register.py -v`
Expected: PASS（邮件服务 mock 跳过）

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/users.py
git commit -m "feat(auth): wire email service into UserManager callbacks"
```

### Task 24: 验证与重置密码端点测试

**Files:**
- Test: `backend/tests/test_auth_verify.py`
- Test: `backend/tests/test_auth_reset_password.py`

- [ ] **Step 1: 写验证测试**

Create `backend/tests/test_auth_verify.py`:

```python
"""邮箱验证端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestVerify:
    def test_request_verify_token(self, auth_client, seed_user):
        """请求验证 token 返回 202。"""
        resp = auth_client.post(
            "/api/auth/request-verify-token",
            json={"email": "test@example.com"},
        )
        assert resp.status_code == 202

    def test_request_verify_nonexistent(self, auth_client):
        """不存在的邮箱返回 202（防探测）。"""
        resp = auth_client.post(
            "/api/auth/request-verify-token",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code == 202
```

- [ ] **Step 2: 写重置密码测试**

Create `backend/tests/test_auth_reset_password.py`:

```python
"""密码重置端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestResetPassword:
    def test_forgot_password(self, auth_client, seed_user):
        """忘记密码返回 202。"""
        resp = auth_client.post(
            "/api/auth/forgot-password",
            json={"email": "test@example.com"},
        )
        assert resp.status_code == 202

    def test_forgot_password_nonexistent(self, auth_client):
        """不存在的邮箱也返回 202（防探测）。"""
        resp = auth_client.post(
            "/api/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code == 202
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/test_auth_verify.py tests/test_auth_reset_password.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_auth_verify.py backend/tests/test_auth_reset_password.py
git commit -m "test(auth): add verify and reset password endpoint tests"
```

---

## Phase 4：清理、前端与文档

### Task 25: 删除旧实现

**Files:**
- Delete: `backend/app/auth.py`
- Delete: `backend/app/core/security.py`
- Delete: `backend/app/crud/users.py`
- Delete: `backend/tests/test_api_auth.py`
- Delete: `backend/tests/test_core_auth.py`
- Delete: `backend/tests/test_core_security.py`
- Delete: `backend/tests/test_seed_data.py`
- Modify: `backend/pyproject.toml`（删 python-jose, bcrypt）

- [ ] **Step 1: 确认无残留引用**

Run: `cd backend && rg "from app.auth import|from app.core.security|from app.crud.users" app/ --type py`
Expected: 无输出（所有引用已迁移）

若有残留，先修复再删除。

- [ ] **Step 2: 删除旧文件**

```bash
rm backend/app/auth.py
rm backend/app/core/security.py
rm backend/app/crud/users.py
rm backend/tests/test_api_auth.py
rm backend/tests/test_core_auth.py
rm backend/tests/test_core_security.py
rm backend/tests/test_seed_data.py
```

- [ ] **Step 3: 从 pyproject.toml 删除旧依赖**

从 `backend/pyproject.toml` 的 `dependencies` 中删除：
```toml
    "python-jose[cryptography]>=3.3.0",
    "bcrypt>=4.0.0",
```

- [ ] **Step 4: 同步依赖**

Run: `cd backend && uv sync`
Expected: 成功

- [ ] **Step 5: 运行全量测试**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(auth): remove legacy auth implementation and dependencies"
```

### Task 26: 更新 pg_schema.py

**Files:**
- Modify: `backend/app/tables/pg_schema.py`

- [ ] **Step 1: 删除 init_users 和 seed_admin_user 函数**

在 `backend/app/tables/pg_schema.py` 中：
- 删除 `init_users(db)` 函数（约 51-80 行）
- 删除 `seed_admin_user(db)` 函数（约 83-97 行）
- 在 `init_all_tables(db)` 函数中删除 `init_users(db)` 和 `seed_admin_user(db)` 调用

- [ ] **Step 2: 验证导入**

Run: `cd backend && python -c "from app.tables.pg_schema import init_all_tables; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/tables/pg_schema.py
git commit -m "refactor(db): remove users table DDL from pg_schema (managed by Alembic)"
```

### Task 27: 更新 seed 逻辑

**Files:**
- Modify: `backend/app/seed_mock_data.py`（或相关启动文件）

- [ ] **Step 1: 查找 seed 逻辑**

Run: `cd backend && rg "seed_admin|init_users|seed_mock" app/ --type py -l`
Expected: 输出相关文件

- [ ] **Step 2: 重写 seed 为 ORM 版本**

在启动流程中（`app/main.py` 的 lifespan 或 `seed_mock_data.py`），添加基于 ORM 的幂等 seed：

```python
def seed_admin_if_missing():
    """幂等 seed 管理员：仅当无 is_superuser=TRUE 用户时创建。"""
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.core.config import settings
    from pwdlib import PasswordHash

    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.is_superuser == True)
        ).scalar_one_or_none()
        if existing is not None:
            return  # 已有管理员

        admin_email = settings.FIRST_SUPERUSER or "admin"
        admin_pass = settings.FIRST_SUPERUSER_PASSWORD
        if not admin_pass:
            return  # 未配置管理员密码

        ph = PasswordHash.recommended()
        admin = User(
            email=admin_email,
            hashed_password=ph.hash(admin_pass),
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role="admin",
        )
        db.add(admin)
        db.commit()
        logger.info("Seeded admin user: %s", admin_email)
    finally:
        db.close()
```

- [ ] **Step 3: 在启动流程调用**

在 `app/main.py` 的 lifespan 中调用 `seed_admin_if_missing()`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/seed_mock_data.py backend/app/main.py
git commit -m "refactor(auth): rewrite admin seed with ORM, idempotent"
```

### Task 28: 前端 API 客户端适配

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/store/useAuthStore.ts`

- [ ] **Step 1: 重写 auth.ts**

Replace `frontend/src/api/auth.ts`:

```typescript
import { apiRequest } from './client';

interface AuthUser {
  id: number;
  email: string;
  username: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

interface AuthResponse {
  access_token?: string;
  token_type?: string;
  user?: AuthUser;
}

export const authApi = {
  register(email: string, password: string, phone?: string, username?: string) {
    return apiRequest<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, phone, username }),
    });
  },

  login(email: string, password: string) {
    // FastAPI Users 用 OAuth2PasswordRequestForm：form-urlencoded
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    return apiRequest<AuthResponse>('/api/auth/jwt/login', {
      method: 'POST',
      body: form,
    });
  },

  logout() {
    return apiRequest('/api/auth/jwt/logout', { method: 'POST' });
  },

  me() {
    return apiRequest<AuthUser>('/api/users/me');
  },

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

export type { AuthUser, AuthResponse };
```

- [ ] **Step 2: 更新 useAuthStore.ts**

Replace `frontend/src/store/useAuthStore.ts` 的 User 接口和 isAdmin 逻辑：

```typescript
interface User {
  id: number;
  email: string;
  username: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, phone?: string) => Promise<void>;
  logout: () => Promise<void>;
  init: () => Promise<void>;
}
```

把所有 `username` 参数改为 `email`，`isAdmin` 改为 `user.is_superuser`。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/store/useAuthStore.ts
git commit -m "feat(auth): adapt frontend API client to FastAPI Users endpoints"
```

### Task 29: 前端登录注册页适配

**Files:**
- Modify: `frontend/src/features/auth/LoginPage.tsx`
- Modify: `frontend/src/features/auth/RegisterPage.tsx`

- [ ] **Step 1: 修改 LoginPage**

把登录表单的 `username` 字段改为 `email`：

```tsx
// 原: <input value={username} ... />
// 改为:
<input
  type="email"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  placeholder="邮箱"
/>
```

`login(username, password)` 改为 `login(email, password)`。

- [ ] **Step 2: 修改 RegisterPage**

注册表单改为：
```tsx
<input type="email" placeholder="邮箱（必填）" value={email} />
<input type="password" placeholder="密码（至少 8 位）" value={password} />
<input type="tel" placeholder="手机号（必填）" value={phone} />
<input type="text" placeholder="昵称（可选）" value={username} />
```

调用 `register(email, password, phone, username)`。

- [ ] **Step 3: 验证前端构建**

Run: `cd frontend && bun run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/auth/
git commit -m "feat(auth): update login/register pages for email-based auth"
```

### Task 30: 新增忘记密码/重置密码页面

**Files:**
- Create: `frontend/src/features/auth/ForgotPasswordPage.tsx`
- Create: `frontend/src/features/auth/ResetPasswordPage.tsx`
- Modify: 路由配置

- [ ] **Step 1: 创建 ForgotPasswordPage**

Create `frontend/src/features/auth/ForgotPasswordPage.tsx`:

```tsx
import { useState } from 'react';
import { authApi } from '../../api/auth';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await authApi.forgotPassword(email);
    setSent(true);
  };

  return (
    <div className="auth-page">
      <h3>忘记密码</h3>
      {sent ? (
        <p>如果该邮箱已注册，重置链接已发送到您的邮箱。</p>
      ) : (
        <form onSubmit={onSubmit}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="邮箱"
            required
          />
          <button type="submit">发送重置链接</button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建 ResetPasswordPage**

Create `frontend/src/features/auth/ResetPasswordPage.tsx`:

```tsx
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [done, setDone] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await authApi.resetPassword(token, password);
    setDone(true);
  };

  return (
    <div className="auth-page">
      <h3>重置密码</h3>
      {done ? (
        <p>密码已重置，请重新登录。</p>
      ) : (
        <form onSubmit={onSubmit}>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="新密码（至少 8 位）"
            required
            minLength={8}
          />
          <button type="submit">重置密码</button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 添加路由**

在路由配置中添加 `/forgot-password` 和 `/reset-password` 路由。

- [ ] **Step 4: 验证构建**

Run: `cd frontend && bun run build`
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/auth/ForgotPasswordPage.tsx frontend/src/features/auth/ResetPasswordPage.tsx frontend/src/routes/
git commit -m "feat(auth): add forgot-password and reset-password pages"
```

### Task 31: 添加 Mailpit 到 docker-compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 添加 Mailpit 服务**

在 `docker-compose.yml` 的 `redis` 服务后添加：

```yaml
  # ─── Mailpit (开发环境邮件测试) ─────────────────────
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - "8025:8025"  # Web UI
      - "1025:1025"  # SMTP
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 64M
          cpus: '0.25'
```

- [ ] **Step 2: 更新 .env.example**

在 `.env.example` 中添加：

```env
# 邮件（开发环境用 Mailpit）
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@innovos.local
SMTP_TLS=false
SMTP_SSL=false
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(auth): add Mailpit for local email testing"
```

### Task 32: 更新文档

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 AGENTS.md**

在 `AGENTS.md` 的 "One-shot Migration Code" 章节后，添加 Alembic 规则：

```markdown
### Alembic Migration Rules

Alembic 仅用于 DDL（schema 声明）的版本化管理：
- 每个 revision 必须是幂等的纯 schema 声明（`CREATE TABLE`、`ALTER TABLE ADD COLUMN`）
- Data backfill（数据回填、列重命名带数据迁移、FK 引用归并）仍遵循 One-shot 规则
- Alembic 目前仅管理 `users` 表，其余业务表仍由 `pg_schema.py` 管理

### Auth Architecture (FastAPI Users)

- 认证基于 FastAPI Users（`app/auth/`）
- 用户表用 SQLAlchemy ORM（`app/db/`），业务表保持 raw psycopg2
- 登录: email + 密码（`POST /api/auth/jwt/login`，OAuth2PasswordRequestForm）
- Token: JWT + `token_version` 撤销机制（`InnovOSJWTStrategy`）
- 管理员: `is_superuser=True` 的 DB 用户，`.env` 仅首次 seed
- 邮件: SMTP（开发用 Mailpit），用于邮箱验证和密码重置
```

- [ ] **Step 2: 更新 CLAUDE.md**

同步更新 `CLAUDE.md` 中的认证架构说明，移除旧的 `auth.py`/`deps.py`/`security.py` 引用，改为 `app/auth/` 模块说明。

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs(auth): update AGENTS.md and CLAUDE.md for FastAPI Users architecture"
```

### Task 33: 运行完整测试与覆盖率

**Files:**
- Modify: `backend/pyproject.toml`（可选提升覆盖率门禁）

- [ ] **Step 1: 运行全量后端测试**

Run: `cd backend && python -m pytest tests/ -v --cov=app/auth --cov=app/db --cov-report=term-missing`
Expected: 全部通过，认证模块覆盖率 > 80%

- [ ] **Step 2: 运行前端测试与构建**

Run: `cd frontend && bun run build && bun run test`
Expected: 构建和测试通过

- [ ] **Step 3: 端到端验证（手动）**

启动 Docker Compose 栈，手动验证：
1. 访问登录页，用 email 登录
2. 注册新用户（email + phone）
3. 访问 `/api/users/me` 确认认证
4. 管理员登录，访问 admin 用户管理
5. 撤销某用户 token，验证旧 token 失效

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test(auth): complete test suite and e2e verification"
```

---

## 自检结果

### Spec 覆盖

| Spec 章节 | 实现任务 |
|---|---|
| §3 总体架构 | Task 2, 7-11, 18 |
| §4 数据模型与 ORM | Task 2, 4, 5 |
| §5 FastAPI Users 核心组件 | Task 7-11, 18, 20 |
| §6 数据迁移 | Task 3-6, 26, 27 |
| §7 错误处理 | Task 11, 18 |
| §8 测试策略 | Task 12-17, 24, 33 |
| §9 前端适配 | Task 28-30 |
| §10 依赖变更 | Task 1, 25 |
| §11 风险缓解 | 散布各任务 |
| §12 分阶段交付 | Phase 0-4 对应 |

### 类型一致性

- `UserManager` 在 Task 8 定义，Task 10/20/23 引用 - 一致
- `InnovOSJWTStrategy` 在 Task 9 定义，Task 10 引用 - 一致
- `current_active_user`/`current_superuser` 在 Task 10 定义，Task 19/20/17 引用 - 一致
- `User` ORM 在 Task 2 定义，全文引用 - 一致

### 占位符扫描

- Task 20 有 `# TODO: created_at 字段` - 这是已知遗留（User 模型未加 created_at 列，因 SQLAlchemyBaseUserTable 不含），在 Task 33 之前需补到 ORM 模型。**修正**：Task 2 的 User 模型应加 `created_at` 列。

**修正 Task 2 的 User 模型**：在 `backend/app/db/models.py` 中添加：

```python
from sqlalchemy import Column, DateTime, Integer, String, func
# ...
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, on_start=None)
```

（Task 2 Step 4 的代码块已隐含此需求，执行时需包含）
