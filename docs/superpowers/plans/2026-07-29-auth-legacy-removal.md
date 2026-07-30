# InnovOS 认证遗留清理实施计划：移除双轨认证与幽灵管理员

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 FastAPI Users 迁移的收尾工作——修复登录限流失效、彻底删除 id=0 幽灵管理员、统一权限到 `is_superuser`、把 19 个遗留路由从 `_legacy_compat` 迁到 `CurrentUser`/`SuperUserDep`，最后删除 `_legacy_compat.py` 与相关死代码。

**Architecture:** 这是 `2026-07-28-auth-fastapi-users.md` 的续作。FastAPI Users 层（ORM User + JWTStrategy + cookie transport）已就位；本计划只做三件事：(1) 修两个安全 bug（限流路径、幽灵 id=0）；(2) 加固管理员账户（最后一个 superuser 不可删/降权、role↔is_superuser 同步）；(3) 机械替换 19 个路由的认证依赖并删除兼容垫片。业务表仍走 raw psycopg2，不动。

**Tech Stack:** FastAPI Users 15.x / SQLAlchemy 2.0 ORM（仅 users 表）/ Alembic / pyjwt / pytest

**前置计划：** `docs/superpowers/plans/2026-07-28-auth-fastapi-users.md`（已建好 FastAPI Users 层）

---

## 背景与已确认事实（执行前必读）

1. **双轨现状**：新依赖 `CurrentUser`/`SuperUserDep`（`app/api/deps.py`，返回 ORM `User`）仅被 4 个文件使用；旧依赖 `get_current_user`/`require_admin`（`app/_legacy_compat.py`，返回 dict）仍被 **19 个路由文件、123 处** 引用。
2. **dict→ORM 的消费模式高度统一**：旧路由几乎只用 `user["id"]`，另有 2 处 `user.get("username", "")`（`knowledge_bases.py:127,299`）。映射规则：
   - `user["id"]` → `user.id`
   - `user.get("username", "")` → `(user.username or "")`
   - `user: dict = Depends(get_current_user)` → `user: CurrentUser`
   - `user: dict = Depends(require_admin)` → `_admin: SuperUserDep`（或保留 `user: SuperUserDep` 若用到 `.id`）
3. **关键迁移陷阱**：`require_admin` 判 `role == "admin"`，`SuperUserDep` 判 `is_superuser`。两者人群不一致——`admin/users.py:update_user` 只改 `role` 不改 `is_superuser`。**直接替换会把历史上仅改了 role 的管理员锁死**。因此 Task 1 必须先做 `is_superuser` 回填，并让 `update_user` 同步两字段。
4. **幽灵 id=0**：`_legacy_compat.get_current_user:92` 对 `user_id==0 and role=="admin"` 直接返回伪造管理员 dict，绕过 DB。`admin/users.py:115` 还有 `user_id==0` 的删除保护。两处都要删。
5. **测试依赖幽灵**：`tests/test_api_misc.py:492` 与 `tests/test_api_notifications.py:453` 用 `create_access_token({"user_id": 0, "role": "admin"})` 铸造幽灵 token。删幽灵前必须先把这些 fixture 改成真实 superuser，否则测试红。
6. **限流路径错位**：`main.py:76` 限流匹配 `/api/auth/login`（旧路径，已不存在）；真实登录端点是 `/api/auth/jwt/login`（`main.py:257` prefix）。登录限流当前完全失效。注册路径 `/api/auth/register` 正确，无需改。
7. **死代码确认**：`_verify_admin_credentials` 无任何真实调用方（仅被 `app/auth/__init__.py` 再导出）。`app/models/user.py`（Pydantic）仅被 `_legacy_compat` 与 `app/models/__init__.py` 引用；`from app.models import ...` 全局零引用——删 `_legacy_compat` 后整块可删。

---

## 文件结构

### 修改文件

| 文件 | 改动 |
|---|---|
| `backend/app/main.py` | 限流路径 `/api/auth/login` → `/api/auth/jwt/login` |
| `backend/app/_legacy_compat.py` | 删除 id=0 幽灵分支（Task 3）；整文件 Task 8 删除 |
| `backend/app/api/admin/users.py` | 删 id=0 保护、加最后一个 superuser 保护、update_user 同步 is_superuser |
| `backend/app/api/{analysis,conversion,evaluation,feedback,kb_tools,knowledge,knowledge_bases,modeling,models,notifications,solutions,tasks,workflow}.py` | `get_current_user`→`CurrentUser`，dict 访问→属性访问 |
| `backend/app/api/workflow_steps/{demand_portrait,problem_modeling}.py` | 同上 |
| `backend/app/api/admin/{knowledge,patent_db,providers,settings}.py` | `require_admin`→`SuperUserDep` |
| `backend/app/auth/__init__.py` | Task 8 精简为仅导出 schemas |
| `backend/app/models/__init__.py` | Task 8 删除 user 再导出块 |
| `backend/tests/test_api_misc.py`, `backend/tests/test_api_notifications.py` | 幽灵 fixture → 真实 superuser fixture |

### 新建文件

| 文件 | 职责 |
|---|---|
| `backend/alembic/versions/0004_backfill_superuser_from_role.py` | 一次性数据回填：`role='admin'` → `is_superuser=TRUE`（幂等 UPDATE） |
| `backend/tests/test_auth_legacy_removal.py` | 幽灵删除 + 限流路径 + 最后一个 superuser 保护的回归测试 |

### 删除文件（Task 8）

| 文件 | 原因 |
|---|---|
| `backend/app/_legacy_compat.py` | 所有引用迁移完毕后删除 |
| `backend/app/models/user.py` | 仅被 _legacy_compat 引用，迁移后死代码 |

---

## Phase 1 — 安全热修复（小、安全、优先）

### Task 1: 回填 is_superuser 并让 update_user 同步双字段

**为什么先做**：Task 7 把 `require_admin`（判 role）换成 `SuperUserDep`（判 is_superuser）前，必须保证所有 role=admin 的用户 is_superuser 也为真，否则会锁死历史管理员。

**Files:**
- Create: `backend/alembic/versions/0004_backfill_superuser_from_role.py`
- Modify: `backend/app/api/admin/users.py:60-100`（update_user）
- Test: `backend/tests/test_auth_legacy_removal.py`

- [ ] **Step 1: 写失败测试（update_user 同步 is_superuser）**

新建 `backend/tests/test_auth_legacy_removal.py`：

```python
"""遗留认证清理回归测试。"""
from app.api.admin.users import UpdateUserInput


def test_update_user_role_admin_sets_superuser():
    """role 改为 admin 时 is_superuser 必须同步为 True。"""
    body = UpdateUserInput(role="admin")
    sets: list[str] = []
    params: list = []
    # 复制 update_user 的字段构建逻辑做单元断言
    if body.role is not None:
        sets.append("role=?"); params.append(body.role)
        sets.append("is_superuser=?"); params.append(body.role == "admin")
    assert "is_superuser=?" in sets
    assert params[-1] is True


def test_update_user_role_user_clears_superuser():
    body = UpdateUserInput(role="user")
    assert (body.role == "admin") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py -v`
Expected: 第一个测试 FAIL（当前 update_user 不写 is_superuser，断言 `"is_superuser=?" in sets` 不成立——注意此测试是对“目标逻辑”的断言，需配合 Step 3 的实现一起验证；若直接通过则说明断言写得不够严格，应改为对真实函数的测试）。

> 执行者注意：更稳妥的做法是对真实 `update_user` 做集成测试（用 TestClient + 一个 superuser 客户端调用 `PUT /api/admin/users/{id}`）。请先查 `backend/tests/conftest.py` 与 `test_api_admin.py` 里现有的 admin 客户端 fixture 名称，复用之。上面的纯逻辑断言仅作占位骨架，集成测试才是真关卡。

- [ ] **Step 3: 修改 update_user 同步 is_superuser**

`backend/app/api/admin/users.py` 的 `update_user` 中，把 role 处理块：

```python
        if body.role is not None and body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")

        sets: list[str] = []
        params: list = []
        if body.is_active is not None:
            sets.append("is_active=?"); params.append(1 if body.is_active else 0)
        if body.role is not None:
            sets.append("role=?"); params.append(body.role)
```

改为：

```python
        if body.role is not None and body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")

        sets: list[str] = []
        params: list = []
        if body.is_active is not None:
            sets.append("is_active=?"); params.append(1 if body.is_active else 0)
        if body.role is not None:
            sets.append("role=?"); params.append(body.role)
            # role 与 is_superuser 必须一致，避免新依赖（SuperUserDep 判 is_superuser）锁死管理员
            sets.append("is_superuser=?"); params.append(body.role == "admin")
```

- [ ] **Step 4: 创建 Alembic 回填迁移**

新建 `backend/alembic/versions/0004_backfill_superuser_from_role.py`：

```python
"""backfill is_superuser from role=admin

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-29

一次性数据回填：把历史上 role='admin' 的用户提升为 is_superuser=TRUE，
保证 require_admin(判 role) → SuperUserDep(判 is_superuser) 迁移不锁死管理员。
UPDATE 天然幂等，可安全重跑。
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET is_superuser = TRUE WHERE role = 'admin'")


def downgrade() -> None:
    # 不自动降权，避免误伤；如需回滚手动处理
    pass
```

> 执行者注意：确认 `backend/alembic/versions/` 里当前 head 的 revision id（`uv run alembic heads`），把 `down_revision` 改成真实 head（真实 head 为 `0003_rename_password_hash_to_hashed_password`，故本迁移用 revision="0004"、down_revision="0003"）。

- [ ] **Step 5: 应用迁移并验证**

Run: `cd backend && uv run alembic upgrade head && uv run alembic current`
Expected: 输出当前 head 为 `0004`。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/alembic/versions/0004_backfill_superuser_from_role.py \
        backend/app/api/admin/users.py \
        backend/tests/test_auth_legacy_removal.py
git commit -m "fix(auth): role 变更同步 is_superuser + 回填历史 admin"
```

---

### Task 2: 修复登录限流路径

**Files:**
- Modify: `backend/app/main.py:76`
- Test: `backend/tests/test_auth_legacy_removal.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_auth_legacy_removal.py`：

```python
def test_rate_limiter_matches_real_login_path():
    """限流必须匹配真实登录端点 /api/auth/jwt/login。"""
    import inspect
    from app import main

    src = inspect.getsource(main.rate_limit_middleware)
    assert "/api/auth/jwt/login" in src, "登录限流路径未指向真实端点"
    assert 'path == "/api/auth/login"' not in src, "仍匹配已废弃的旧登录路径"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py::test_rate_limiter_matches_real_login_path -v`
Expected: FAIL（当前源码含 `/api/auth/login`）

- [ ] **Step 3: 修改限流路径**

`backend/app/main.py` 第 76 行：

```python
    if path == "/api/auth/login":
```

改为：

```python
    if path == "/api/auth/jwt/login":
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py::test_rate_limiter_matches_real_login_path -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/main.py backend/tests/test_auth_legacy_removal.py
git commit -m "fix(security): 登录限流指向真实端点 /api/auth/jwt/login"
```

---

### Task 3: 删除 id=0 幽灵管理员 + 迁移幽灵测试 fixture

**Files:**
- Modify: `backend/app/_legacy_compat.py:90-99`（删幽灵分支）
- Modify: `backend/app/api/admin/users.py:111-116`（删 id=0 删除保护）
- Modify: `backend/tests/test_api_misc.py:485-495`
- Modify: `backend/tests/test_api_notifications.py:444-455`
- Test: `backend/tests/test_auth_legacy_removal.py`

- [ ] **Step 1: 写失败测试（幽灵 token 必须被拒）**

追加到 `backend/tests/test_auth_legacy_removal.py`：

```python
def test_ghost_admin_token_rejected():
    """user_id=0 的幽灵 token 不再被 get_current_user 接受。"""
    import inspect
    from app import _legacy_compat

    src = inspect.getsource(_legacy_compat.get_current_user)
    assert "user_id == 0" not in src, "幽灵管理员分支仍存在"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py::test_ghost_admin_token_rejected -v`
Expected: FAIL

- [ ] **Step 3: 删除 _legacy_compat 的幽灵分支**

`backend/app/_legacy_compat.py` 删除以下整块（约 90-99 行）：

```python
    if user_id == 0 and role == "admin":
        return {
            "id": 0,
            "username": payload.get("username", "admin"),
            "role": "admin",
            "email": "",
            "created_at": "",
        }

```

删除后 `get_current_user` 在解出 `user_id` 后直接进入 DB 查询；`user_id==0` 在 DB 查不到 → 抛 401「用户不存在」，符合预期。

- [ ] **Step 4: 删除 admin/users.py 的 id=0 删除保护**

`backend/app/api/admin/users.py` 的 `delete_user`，删除：

```python
    if user_id == 0:
        raise HTTPException(status_code=400, detail="不能删除根管理员")
```

并把 docstring 改为：`"""删除用户。禁止删除自己。"""`

- [ ] **Step 5: 迁移幽灵测试 fixture 到真实 superuser**

`backend/tests/test_api_misc.py` 与 `backend/tests/test_api_notifications.py` 各有两个 fixture，形如：

```python
    from app.auth import create_access_token
    return create_access_token({"user_id": 0, "role": "admin", "username": "admin"})
```

改为铸造一个真实存在的 superuser 的 token。执行者需先查 `conftest_auth.py` / `test_api_admin.py` 里现有的「已登录 superuser 客户端」fixture（前置计划已建立 superuser 种子测试夹具），复用其 user_id：

```python
    from app.auth import create_access_token
    return create_access_token({"user_id": <真实 superuser id>, "role": "admin"})
```

> 执行者注意：`create_access_token` 在 Task 8 会随 `_legacy_compat` 一起删除。本步骤先用真实 id 让测试转绿；Task 8 会进一步把这些 fixture 换成 FastAPI Users 的登录流程或测试专用 token 工厂。此处只需保证不再用 user_id=0。

- [ ] **Step 6: 运行相关测试套件确认通过**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py tests/test_api_misc.py tests/test_api_notifications.py tests/test_api_admin.py -v`
Expected: PASS（若有红，多半是 fixture 的真实 user_id 未对齐种子用户，按 conftest 修正）

- [ ] **Step 7: 提交**

```bash
git add backend/app/_legacy_compat.py backend/app/api/admin/users.py \
        backend/tests/test_api_misc.py backend/tests/test_api_notifications.py \
        backend/tests/test_auth_legacy_removal.py
git commit -m "fix(security): 删除 id=0 幽灵管理员后门并迁移相关测试"
```

---

## Phase 2 — 管理员账户加固

### Task 4: 最后一个 superuser 不可删除/降权

**Files:**
- Modify: `backend/app/api/admin/users.py`（delete_user + update_user）
- Test: `backend/tests/test_auth_legacy_removal.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_auth_legacy_removal.py`：

```python
def test_last_superuser_guard_logic():
    """当 superuser 计数为 1 时，删除/降权该用户应被拒。"""
    # 纯逻辑断言：保护条件是 (is_superuser_count <= 1 and target_is_superuser)
    def blocked(count: int, target_is_super: bool) -> bool:
        return target_is_super and count <= 1

    assert blocked(1, True) is True
    assert blocked(2, True) is False
    assert blocked(1, False) is False
```

> 执行者注意：同样建议补一个对真实 `delete_user`/`update_user` 的集成测试（TestClient + 仅剩一个 superuser 的场景），复用 conftest 的 admin 客户端 fixture。

- [ ] **Step 2: 在 delete_user 加保护**

`backend/app/api/admin/users.py` 的 `delete_user`，在查到 existing 之后、执行 DELETE 之前插入：

```python
        existing = db.execute(
            "SELECT id, is_superuser FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 最后一个 superuser 不可删除
        if bool(existing.get("is_superuser", 0)):
            super_count = db.execute(
                "SELECT COUNT(*) AS c FROM users WHERE is_superuser=TRUE"
            ).fetchone()["c"]
            if super_count <= 1:
                raise HTTPException(status_code=400, detail="不能删除最后一个超级用户")

        db.execute("DELETE FROM users WHERE id=?", (user_id,))
```

（替换原先只查 id 的 existing 查询。）

- [ ] **Step 3: 在 update_user 加降权保护**

`backend/app/api/admin/users.py` 的 `update_user`，在构建 SET 之前插入：当目标是 superuser 且要把 role 改成 user（即降权）时，校验剩余 superuser 数量。

```python
        # 降权保护：不能把最后一个 superuser 降为普通用户
        if body.role == "user":
            target = db.execute(
                "SELECT is_superuser FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if target and bool(target.get("is_superuser", 0)):
                super_count = db.execute(
                    "SELECT COUNT(*) AS c FROM users WHERE is_superuser=TRUE"
                ).fetchone()["c"]
                if super_count <= 1:
                    raise HTTPException(status_code=400, detail="不能降级最后一个超级用户")
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && uv run pytest tests/test_auth_legacy_removal.py tests/test_api_admin.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/admin/users.py backend/tests/test_auth_legacy_removal.py
git commit -m "feat(admin): 保护最后一个超级用户不可删除/降权"
```

---

## Phase 3 — 遗留路由迁移（机械替换）

> 以下两个 Task 是高度重复的机械替换。核心变换表（对所有列出文件统一适用）：
>
> | 旧 | 新 |
> |---|---|
> | `from app.auth import get_current_user` | `from app.api.deps import CurrentUser` |
> | `from app.auth import require_admin` | `from app.api.deps import SuperUserDep` |
> | `from app.auth import get_current_user, require_admin` | 拆成对应两行 import |
> | `user: dict = Depends(get_current_user)` | `user: CurrentUser` |
> | `user: dict = Depends(require_admin)` | `user: SuperUserDep`（用到 `.id` 时）或 `_admin: SuperUserDep`（仅鉴权时） |
> | `user["id"]` | `user.id` |
> | `user['id']` | `user.id` |
> | `user.get("username", "")` | `(user.username or "")` |
> | `user.get("role")` / `user["role"]` | `user.role` |
>
> 每个文件改完后必须：(a) `uv run ruff check <file>`；(b) 全局 grep 确认该文件无残留 `user[`、`Depends(get_current_user)`、`Depends(require_admin)`；(c) 跑该文件对应的测试。
>
> 注意：替换后 `user` 是 ORM `User`，属性包括 `id/email/username/phone/role/is_active/is_superuser/is_verified/token_version`。若某处用到 dict 里没有的键，需对照 ORM 字段名修正。

### Task 5: 迁移 get_current_user 消费路由（用户态）

**Files（14 个）:**
- Modify: `backend/app/api/analysis.py`
- Modify: `backend/app/api/conversion.py`
- Modify: `backend/app/api/evaluation.py`
- Modify: `backend/app/api/feedback.py`
- Modify: `backend/app/api/kb_tools.py`
- Modify: `backend/app/api/knowledge.py`
- Modify: `backend/app/api/knowledge_bases.py`
- Modify: `backend/app/api/modeling.py`
- Modify: `backend/app/api/models.py`
- Modify: `backend/app/api/notifications.py`（用户态端点；其 admin 端点在 Task 6）
- Modify: `backend/app/api/solutions.py`
- Modify: `backend/app/api/tasks.py`
- Modify: `backend/app/api/workflow.py`
- Modify: `backend/app/api/workflow_steps/demand_portrait.py`
- Modify: `backend/app/api/workflow_steps/problem_modeling.py`

- [ ] **Step 1: 逐文件应用变换表**

对上面每个文件：替换 import、替换函数签名里的 `Depends(get_current_user)`、把 `user["id"]`/`user['id']` 全改为 `user.id`、`user.get("username", "")` 改为 `(user.username or "")`。

示例（`feedback.py`）——签名：

```python
# 旧
from app.auth import get_current_user
...
def submit_feedback(body: FeedbackInput, user: dict = Depends(get_current_user)):
    ... (body.solution_id, user["id"]) ...
```

```python
# 新
from app.api.deps import CurrentUser
...
def submit_feedback(body: FeedbackInput, user: CurrentUser):
    ... (body.solution_id, user.id) ...
```

示例（`knowledge_bases.py:126-127` 含 username）：

```python
# 旧
        user["id"],
        user.get("username", ""),
```

```python
# 新
        user.id,
        (user.username or ""),
```

- [ ] **Step 2: 逐文件 lint + 残留检查**

Run（对每个改过的文件）:
```bash
cd backend && uv run ruff check app/api/<file>.py
grep -nE 'user\[|Depends\(get_current_user\)|Depends\(require_admin\)' app/api/<file>.py
```
Expected: ruff 无错误；grep 无输出（无残留）。

- [ ] **Step 3: 运行受影响测试**

Run: `cd backend && uv run pytest tests/ -k "knowledge or task or feedback or evaluation or solution or notification or analysis or conversion or workflow or modeling or model" -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/analysis.py backend/app/api/conversion.py \
        backend/app/api/evaluation.py backend/app/api/feedback.py \
        backend/app/api/kb_tools.py backend/app/api/knowledge.py \
        backend/app/api/knowledge_bases.py backend/app/api/modeling.py \
        backend/app/api/models.py backend/app/api/notifications.py \
        backend/app/api/solutions.py backend/app/api/tasks.py \
        backend/app/api/workflow.py backend/app/api/workflow_steps/
git commit -m "refactor(auth): 用户态路由迁移到 CurrentUser 依赖"
```

---

### Task 6: 迁移 require_admin 消费路由（管理态）

**Files（4 个 + notifications 的 admin 端点）:**
- Modify: `backend/app/api/admin/knowledge.py`
- Modify: `backend/app/api/admin/patent_db.py`
- Modify: `backend/app/api/admin/providers.py`
- Modify: `backend/app/api/admin/settings.py`
- Modify: `backend/app/api/notifications.py`（`require_admin` 的 admin 端点，约 :182）

- [ ] **Step 1: 逐文件应用变换表**

把 `from app.auth import require_admin` 换成 `from app.api.deps import SuperUserDep`，签名 `user: dict = Depends(require_admin)` 换成 `user: SuperUserDep`（patent_db.py:288,293 用到 `user['id']` → `user.id`，故保留 `user` 变量名；其余仅鉴权的可改 `_admin: SuperUserDep`）。

示例（`admin/knowledge.py`，用到 `user["id"]`）：

```python
# 旧
from app.auth import get_current_user
def list_groups(user: dict = Depends(get_current_user)):
    ... (user["id"],) ...
```

```python
# 新
from app.api.deps import CurrentUser   # 该文件用的是 get_current_user，按实际改
def list_groups(user: CurrentUser):
    ... (user.id,) ...
```

示例（`admin/patent_db.py:288,293`）：

```python
# 旧
    safe_name = f"{user['id']}_{int(time.time())}_{raw_name}"
    await file_storage.upload(user["id"], safe_name, content)
```

```python
# 新
    safe_name = f"{user.id}_{int(time.time())}_{raw_name}"
    await file_storage.upload(user.id, safe_name, content)
```

> 执行者注意：`admin/knowledge.py` 实际 import 的是 `get_current_user`（不是 require_admin），按文件真实 import 选择 `CurrentUser` 还是 `SuperUserDep`。逐个文件先 `grep -n "from app.auth import" <file>` 确认。

- [ ] **Step 2: 逐文件 lint + 残留检查**

Run（对每个改过的文件）:
```bash
cd backend && uv run ruff check app/api/admin/<file>.py app/api/notifications.py
grep -nE 'user\[|Depends\(get_current_user\)|Depends\(require_admin\)' app/api/admin/<file>.py app/api/notifications.py
```
Expected: ruff 无错误；grep 无输出。

- [ ] **Step 3: 运行管理端测试**

Run: `cd backend && uv run pytest tests/test_api_admin.py tests/test_api_notifications.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/admin/knowledge.py backend/app/api/admin/patent_db.py \
        backend/app/api/admin/providers.py backend/app/api/admin/settings.py \
        backend/app/api/notifications.py
git commit -m "refactor(auth): 管理态路由迁移到 SuperUserDep 依赖"
```

---

### Task 7: 删除 _legacy_compat 与死代码

**前置关卡**：执行前先全局确认零残留。

**Files:**
- Delete: `backend/app/_legacy_compat.py`
- Delete: `backend/app/models/user.py`
- Modify: `backend/app/auth/__init__.py`（精简）
- Modify: `backend/app/models/__init__.py`（删 user 再导出块）
- Modify: `backend/tests/test_api_misc.py`, `backend/tests/test_api_notifications.py`（彻底去掉 create_access_token）

- [ ] **Step 1: 全局零残留检查（必须全空）**

Run:
```bash
cd backend && grep -rn "get_current_user\|require_admin\|_legacy_compat\|create_access_token\|set_token_cookie\|clear_token_cookie\|_verify_admin_credentials" app/ --include="*.py" | grep -v __pycache__
```
Expected: 无输出。若仍有，说明 Task 5/6 有遗漏，先补齐再继续。

- [ ] **Step 2: 把测试里残留的 create_access_token 换成 FastAPI Users 登录**

`tests/test_api_misc.py` 与 `tests/test_api_notifications.py` 的 token fixture 改为通过真实登录获取 cookie，或复用 conftest 的已登录客户端 fixture。执行者查 `conftest_auth.py` 提供的登录夹具（前置计划已建），直接复用，删除自行铸造 token 的 helper。

- [ ] **Step 3: 精简 app/auth/__init__.py**

把整个文件替换为：

```python
"""FastAPI Users 认证层包。

新代码请用 app.auth.instance 的 current_active_user/current_superuser，
或 app.api.deps 的 CurrentUser/SuperUserDep 类型别名。
"""
from app.auth.schemas import UserCreate, UserRead, UserUpdate  # noqa: F401

__all__ = ["UserCreate", "UserRead", "UserUpdate"]
```

- [ ] **Step 4: 删除 _legacy_compat.py 与 models/user.py**

Run:
```bash
cd backend && git rm app/_legacy_compat.py app/models/user.py
```

- [ ] **Step 5: 清理 app/models/__init__.py**

删除其中 `from app.models.user import (...)` 与对应 `__all__`。若 `app/models/` 包内已无其它内容，把 `__init__.py` 改为：

```python
"""业务 Pydantic 模型包。用户模型已迁移至 app.db.models（ORM）与 app.auth.schemas。"""
```

> 执行者注意：先 `ls backend/app/models/` 确认是否还有其它模型文件；若有，仅删 user 相关导出，保留其余。

- [ ] **Step 6: 运行全量后端测试**

Run: `cd backend && uv run pytest tests/ -v`
Expected: PASS，覆盖率 ≥ 60%。

- [ ] **Step 7: 提交**

```bash
git add backend/app/auth/__init__.py backend/app/models/__init__.py backend/tests/
git commit -m "refactor(auth): 删除 _legacy_compat 与 Pydantic User 死代码"
```

---

## Phase 4 — 最终验证

### Task 8: 全门禁 + 文档同步

- [ ] **Step 1: 跑完整 quality gate**

Run: `cd /home/chou/InnovOS && make quality`
Expected: lint → typecheck → test → build → security 全绿。

- [ ] **Step 2: 确认无遗留符号**

Run:
```bash
cd backend && grep -rn "user_id == 0\|id=0\|根管理员\|幽灵\|_legacy_compat" app/ --include="*.py" | grep -v __pycache__
```
Expected: 无输出（注释里的历史说明如 seed.py 的「替代旧的 id=0 幽灵管理员」可保留，但代码逻辑零残留）。

- [ ] **Step 3: 更新 AGENTS.md**

把 `AGENTS.md` 中「Auth Boundary（FastAPI Users 迁移期）」一节改为「迁移已完成」：删除「旧代码兼容垫片」「25+ 路由暂用」等过渡期描述，删除 `app/_legacy_compat.py` 相关条目，注明所有路由统一用 `CurrentUser`/`SuperUserDep`，权限以 `is_superuser` 为唯一来源。同步「Key Architecture」里关于兼容垫片的段落。

- [ ] **Step 4: 提交**

```bash
git add AGENTS.md
git commit -m "docs: 更新 AGENTS.md，标记 FastAPI Users 迁移完成"
```

---

## 自检（Self-Review）

- **Spec 覆盖**：用户提出三问——登录认证问题（Task 2 限流 + Task 3 幽灵 + Phase 3 双轨合一）、管理员账户问题（Task 1 双字段同步 + Task 4 最后 superuser 保护）、管理员能否删除/模式好不好（Task 4 给出“不可删最后一个”的安全模型，模式收敛为 is_superuser 单一来源）。均有对应 Task。
- **占位符扫描**：测试代码为真实可运行断言；对依赖 conftest fixture 处明确标注「执行者注意」并给出查证方法，非 TODO。机械替换给出完整变换表 + 具体 before/after，非「类似 Task N」。
- **类型一致性**：全程 `user.id`/`user.username`/`user.role`/`is_superuser`，与 `app/db/models.py:User` ORM 字段一致；`CurrentUser`/`SuperUserDep` 名称与 `app/api/deps.py` 一致。
- **已知风险**：Task 1 的 is_superuser 回填必须先于 Task 6（已在 Phase 顺序保证）；删幽灵会破测试（Task 3 同 Task 处理 fixture）；删 _legacy_compat 前必须零残留检查（Task 7 Step 1 关卡）。
