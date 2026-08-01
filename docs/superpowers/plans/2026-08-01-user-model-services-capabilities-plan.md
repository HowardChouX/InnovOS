# User Model Services — 能力感知通配管理 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `user_model_services` 升级为按能力（chat/embedding/rerank）独立开通和故障转移

**Architecture:** `user_model_services` 表添加 `capability` 列，每条记录变为「供应商+能力」组合；`FailoverRouter` 按能力过滤队列；前端页面按能力分组展示独立列表

**Tech Stack:** PostgreSQL, FastAPI, React 19 + TypeScript

## Global Constraints

- 模型管理（model_providers、api_keys）保持不变
- 现有 `user_model_services` 数据迁移为 `capability='chat'`
- 后端 API 所有端点新增 `capability` 参数
- 前端 `UserModelServicesPage` 改为垂直分组布局
- `FailoverRouter._load_queue()` 新增 `capability` 过滤

---

### Task 1: 数据库迁移 — 添加 capability 列

**Files:**
- Modify: `backend/app/tables/pg_schema.py`
- Create: `backend/alembic/versions/0018_add_capability_to_user_model_services.py`

**Interfaces:**
- Consumes: 现有 `user_model_services` 表结构
- Produces: 新表结构 `(user_id, provider_id, capability, failover_order, is_enabled)`

- [ ] **Step 1: 编写 Alembic 迁移脚本**

```python
"""add capability column to user_model_services

Revision ID: 0018
Revises: 0017_add_user_model_services_and_call_log
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017_add_user_model_services_and_call_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. 添加 capability 列（现有行默认 chat）
    op.execute("""
        ALTER TABLE user_model_services
        ADD COLUMN IF NOT EXISTS capability TEXT NOT NULL DEFAULT 'chat'
    """)
    # 2. 删旧主键 + 唯一约束
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS user_model_services_pkey")
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS user_model_services_user_id_failover_order_key")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_enabled")
    # 3. 建新主键 + 唯一约束 + 索引
    op.execute("""
        ALTER TABLE user_model_services
        ADD PRIMARY KEY (user_id, provider_id, capability)
    """)
    op.execute("""
        ALTER TABLE user_model_services
        ADD CONSTRAINT uq_ums_user_cap_order UNIQUE (user_id, capability, failover_order)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ums_user_cap_enabled
            ON user_model_services (user_id, capability, is_enabled, failover_order)
    """)

def downgrade() -> None:
    op.execute("ALTER TABLE user_model_services DROP CONSTRAINT IF EXISTS uq_ums_user_cap_order")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_cap_enabled")
    op.execute("ALTER TABLE user_model_services DROP COLUMN IF EXISTS capability")
```

- [ ] **Step 2: 更新 pg_schema.py 的 init_user_model_services()**

```python
def init_user_model_services(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_model_services (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            capability TEXT NOT NULL DEFAULT 'chat',
            failover_order INTEGER NOT NULL CHECK (failover_order >= 1),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, provider_id, capability),
            UNIQUE (user_id, capability, failover_order)
        );
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS ix_ums_user_cap_enabled
            ON user_model_services (user_id, capability, is_enabled, failover_order);
    """)
```

- [ ] **Step 3: 运行迁移验证**

```bash
cd backend && uv run alembic upgrade head
```

Expected: 无错误，现有数据保留且 `capability='chat'`

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/0018_add_capability_to_user_model_services.py backend/app/tables/pg_schema.py
git commit -m "feat(db): add capability column to user_model_services"
```

---

### Task 2: FailoverRouter — 按能力过滤队列

**Files:**
- Modify: `backend/app/services/failover_router.py`
- Test: `backend/tests/test_failover_router.py`

**Interfaces:**
- Consumes: `_load_queue(user_id: int)` → `_load_queue(user_id: int, capability: str = "chat")`
- Produces: `FailoverRouter.call()` 新增 `capability` 参数，SQL 增加 `AND ums.capability = %s`

- [ ] **Step 1: 修改 `_load_queue()` 函数**

```python
def _load_queue(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    """Return the user's enabled queue for a given capability, joined with provider + key + health."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.capability,
                mp.api_host,
                mp.api_model,
                ak.id              AS key_id,
                ak.key_ciphertext  AS api_key_ciphertext,
                ak.key_nonce       AS api_key_nonce,
                ak.encryption_version,
                ph.is_healthy,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            JOIN api_keys ak
                 ON ak.provider_id = ums.provider_id
                AND ak.is_active = TRUE
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s
              AND ums.capability = %s
              AND ums.is_enabled = TRUE
              AND mp.is_enabled = 1
              AND ak.priority = 0
            ORDER BY ums.failover_order ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    # ... 其余不变
```

- [ ] **Step 2: 修改 `FailoverRouter.call()` 方法**

```python
async def call(
    self,
    *,
    user_id: int,
    purpose: str,
    messages: list[dict],
    model_override: Optional[str] = None,
) -> dict[str, Any]:
    # 新增：purpose → capability 映射
    capability = _purpose_to_capability(purpose)
    queue = _load_queue(user_id, capability=capability)
    # ... 其余不变
```

- [ ] **Step 3: 添加 `_purpose_to_capability()` 映射函数**

```python
PURPOSE_TO_CAPABILITY: dict[str, str] = {
    "chat": "chat",
    "evaluation": "chat",
    "conversion": "chat",
    "extract": "chat",
    "ocr": "chat",
    "embedding": "embedding",
    "rerank": "rerank",
}

def _purpose_to_capability(purpose: str) -> str:
    return PURPOSE_TO_CAPABILITY.get(purpose, "chat")
```

- [ ] **Step 4: 写测试**

```python
def test_load_queue_filters_by_capability():
    # 准备：用户 10 开通了 deepseek(chat) + deepseek(embedding)
    # 验证：capability='chat' 只返回 1 条
    queue = _load_queue(user_id=10, capability="chat")
    assert len(queue) == 1
    assert queue[0]["provider_id"] == "deepseek"
    
    # 验证：capability='embedding' 只返回 1 条
    queue = _load_queue(user_id=10, capability="embedding")
    assert len(queue) == 1
    assert queue[0]["provider_id"] == "deepseek"
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/failover_router.py
git commit -m "feat: FailoverRouter filters by capability"
```

---

### Task 3: 后端 API — user_model_services 端点支持 capability

**Files:**
- Modify: `backend/app/api/admin/user_model_services.py`

**Interfaces:**
- Consumes: Task 1 的数据库变更
- Produces: 所有端点支持 `capability` 参数

- [ ] **Step 1: 修改 `_load()` 和 `_load_available()` 函数**

```python
def _load(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.capability,
                ums.failover_order,
                ums.is_enabled,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                COALESCE(ph.consecutive_failures, 0) AS consecutive_failures,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s AND ums.capability = %s
            ORDER BY ums.failover_order ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]


def _load_available(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    """返回可开通的供应商列表（尚未开通该能力的）"""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                mp.provider_id,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                EXISTS (
                    SELECT 1 FROM user_model_services ums2
                    WHERE ums2.user_id = %s
                      AND ums2.provider_id = mp.provider_id
                      AND ums2.capability = %s
                ) AS already_enabled
            FROM model_providers mp
            LEFT JOIN provider_health ph ON ph.provider_id = mp.provider_id
            ORDER BY mp.name ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]
```

- [ ] **Step 2: 修改 `_next_order()` 函数**

```python
def _next_order(user_id: int, capability: str = "chat") -> int:
    db = get_db()
    try:
        row = db.execute(
            """SELECT COALESCE(MAX(failover_order), 0) + 1 AS next
               FROM user_model_services
               WHERE user_id=%s AND capability=%s""",
            (user_id, capability),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return 1
    n = row["next"] if isinstance(row, dict) else row[0]
    return int(n or 1)
```

- [ ] **Step 3: 修改所有端点，增加 `capability` 参数**

```python
@router.get("")
def list_user_services(
    user_id: int,
    capability: str = Query("chat", description="能力类型: chat/embedding/rerank"),
    _: dict = Depends(require_admin),
) -> dict:
    return {"data": _load(user_id, capability), "message": "success"}


@router.get("/available")
def list_available_services(
    user_id: int,
    capability: str = Query("chat", description="能力类型: chat/embedding/rerank"),
    _: dict = Depends(require_admin),
) -> dict:
    return {"data": _load_available(user_id, capability), "message": "success"}


class AddBody(BaseModel):
    provider_id: str
    capability: str = "chat"


@router.post("")
def add_user_service(
    user_id: int, body: AddBody, _: dict = Depends(require_admin)
) -> dict:
    db = get_db()
    try:
        existing = db.execute(
            "SELECT failover_order, is_enabled FROM user_model_services "
            "WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (user_id, body.provider_id, body.capability),
        ).fetchone()
        if existing is not None:
            return {"data": _row_to_dict(existing), "message": "already enabled"}
        order = _next_order(user_id, body.capability)
        db.execute(
            "INSERT INTO user_model_services (user_id, provider_id, capability, failover_order, is_enabled) "
            "VALUES (%s, %s, %s, %s, TRUE)",
            (user_id, body.provider_id, body.capability, order),
        )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id, body.capability), "message": "added"}


@router.delete("/{provider_id}", status_code=204)
def remove_user_service(
    user_id: int,
    provider_id: str,
    capability: str = Query("chat"),
    _: dict = Depends(require_admin),
):
    db = get_db()
    try:
        db.execute(
            "DELETE FROM user_model_services WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (user_id, provider_id, capability),
        )
        db.commit()
    finally:
        db.close()
    return None


class ToggleBody(BaseModel):
    is_enabled: bool
    capability: str = "chat"


@router.post("/{provider_id}/toggle")
def toggle_user_service(
    user_id: int, provider_id: str, body: ToggleBody, _: dict = Depends(require_admin)
) -> dict:
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE user_model_services SET is_enabled=%s, updated_at=NOW() "
            "WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (bool(body.is_enabled), user_id, provider_id, body.capability),
        )
        db.commit()
    finally:
        db.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="not enabled")
    return {"data": {"is_enabled": body.is_enabled}, "message": "toggled"}


class OrderBody(BaseModel):
    provider_ids: list[str]
    capability: str = "chat"


@router.put("/order")
def reorder_user_services(
    user_id: int, body: OrderBody, _: dict = Depends(require_admin)
) -> dict:
    new_ids = list(body.provider_ids)
    seen: set[str] = set()
    for pid in new_ids:
        if pid in seen:
            raise HTTPException(status_code=409, detail=f"duplicate provider_id: {pid}")
        seen.add(pid)

    db = get_db()
    try:
        if new_ids:
            placeholders = ",".join(["%s"] * len(new_ids))
            db.execute(
                f"DELETE FROM user_model_services "
                f"WHERE user_id=%s AND capability=%s AND provider_id NOT IN ({placeholders})",
                tuple([user_id, body.capability, *new_ids]),
            )
        else:
            db.execute(
                "DELETE FROM user_model_services WHERE user_id=%s AND capability=%s",
                (user_id, body.capability),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "INSERT INTO user_model_services (user_id, provider_id, capability, failover_order, is_enabled) "
                "VALUES (%s, %s, %s, %s, TRUE) "
                "ON CONFLICT (user_id, provider_id, capability) DO UPDATE SET updated_at=NOW()",
                (user_id, pid, body.capability, offset + 1_000_000),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "UPDATE user_model_services SET failover_order=%s, updated_at=NOW() "
                "WHERE user_id=%s AND provider_id=%s AND capability=%s",
                (offset, user_id, pid, body.capability),
            )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id, body.capability), "message": "reordered"}
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/admin/user_model_services.py
git commit -m "feat: user_model_services API supports capability parameter"
```

---

### Task 4: 前端 API 客户端 — 更新 userModelServices.ts

**Files:**
- Modify: `frontend/src/api/admin/userModelServices.ts`

**Interfaces:**
- Consumes: Task 3 的后端 API 变更
- Produces: 前端 API 方法支持 `capability` 参数

- [ ] **Step 1: 更新接口定义**

```typescript
export interface UserModelService {
  provider_id: string;
  capability: string;
  name: string;
  api_host: string;
  api_model: string;
  failover_order: number;
  is_enabled: boolean;
  is_healthy?: boolean;
  consecutive_failures?: number;
  cooldown_until?: string | null;
}

export interface AvailableModelService {
  provider_id: string;
  name: string;
  api_host: string;
  api_model: string;
  already_enabled: boolean;
  is_healthy?: boolean;
}
```

- [ ] **Step 2: 更新 API 方法，所有调用增加 `capability` 参数**

```typescript
export const userModelServicesApi = {
  list: (userId: number, capability: string = 'chat'): Promise<{ data: UserModelService[] }> =>
    apiRequest<{ data: UserModelService[] }>(
      `/api/admin/users/${userId}/model-services?capability=${encodeURIComponent(capability)}`,
    ),

  listAvailable: (userId: number, capability: string = 'chat'): Promise<{ data: AvailableModelService[] }> =>
    apiRequest<{ data: AvailableModelService[] }>(
      `/api/admin/users/${userId}/model-services/available?capability=${encodeURIComponent(capability)}`,
    ),

  add: (userId: number, providerId: string, capability: string = 'chat'): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services`, {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId, capability }),
    }),

  remove: (userId: number, providerId: string, capability: string = 'chat'): Promise<void> =>
    apiRequest<void>(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}?capability=${encodeURIComponent(capability)}`,
      { method: 'DELETE' },
    ),

  toggle: (
    userId: number,
    providerId: string,
    isEnabled: boolean,
    capability: string = 'chat',
  ): Promise<{ data: { is_enabled: boolean } }> =>
    apiRequest(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}/toggle`,
      {
        method: 'POST',
        body: JSON.stringify({ is_enabled: isEnabled, capability }),
      },
    ),

  reorder: (userId: number, providerIds: string[], capability: string = 'chat'): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services/order`, {
      method: 'PUT',
      body: JSON.stringify({ provider_ids: providerIds, capability }),
    }),
};
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/admin/userModelServices.ts
git commit -m "feat: frontend API client supports capability parameter"
```

---

### Task 5: 前端页面 — 重写 UserModelServicesPage 为能力分组布局

**Files:**
- Modify: `frontend/src/features/admin/UserModelServicesPage.tsx`
- Modify: `frontend/src/features/admin/UserModelServicesPage.test.tsx`

- [ ] **Step 1: 定义能力分组配置**

```typescript
const CAPABILITIES = [
  { key: 'chat',       label: '文本模型',     description: '对话、文本生成、评估等',     status: 'active' as const },
  { key: 'embedding',  label: '嵌入模型',     description: '向量嵌入、语义检索',         status: 'active' as const },
  { key: 'rerank',     label: '重排模型',     description: '相关性重排、精排',           status: 'active' as const },
  { key: 'image',      label: '图片/视频模型', description: '图片生成、视频生成（即将支持）', status: 'coming_soon' as const },
] as const;
```

- [ ] **Step 2: 提取可复用的 `ModelServiceSection` 组件**

每个能力区块是一个独立的 `ModelServiceSection` 组件，功能与当前页面一致（拖拽排序、开通/停用/移除），但数据通过 `capability` 参数隔离。

```typescript
function ModelServiceSection({
  capability,
  label,
  description,
  userId,
  status,
}: {
  capability: string;
  label: string;
  description: string;
  userId: number;
  status: 'active' | 'coming_soon';
}) {
  // 内部独立管理 loading/error/enabled/available 状态
  // 加载时调用 userModelServicesApi.list(userId, capability)
  // 拖拽重排调用 userModelServicesApi.reorder(userId, ids, capability)
  // 与当前页面逻辑相同，只是多了 capability 参数
  if (status === 'coming_soon') {
    return (
      <section>
        <h2>{label}</h2>
        <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>⏳ {description}</p>
      </section>
    );
  }
  // ... 正常渲染已开通/未开通列表
}
```

- [ ] **Step 3: 主页面渲染所有能力分组**

```typescript
export function UserModelServicesPage() {
  const { userId: userIdParam } = useParams<{ userId: string }>();
  const userId = Number(userIdParam);

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1>用户 #{userId} — AI 模型服务</h1>
        <Link to="/admin/users">← 返回用户管理</Link>
      </div>
      {CAPABILITIES.map((cap) => (
        <ModelServiceSection
          key={cap.key}
          capability={cap.key}
          label={cap.label}
          description={cap.description}
          userId={userId}
          status={cap.status}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 更新测试**

更新 `UserModelServicesPage.test.tsx` 以匹配新布局，验证：
- 渲染所有 4 个能力分组
- 每个 active 分组可独立加载/开通/移除
- comings_soon 分组显示占位文案

- [ ] **Step 5: 提交**

```bash
git add frontend/src/features/admin/UserModelServicesPage.tsx frontend/src/features/admin/UserModelServicesPage.test.tsx
git commit -m "feat: rewrite UserModelServicesPage with capability sections"
```

---

### Task 6: 数据迁移 — 填充现有数据

**Files:**
- Execute: SQL 迁移脚本

- [ ] **Step 1: 验证现有数据已正确迁移**

```sql
-- 检查所有行都有 capability
SELECT COUNT(*) FROM user_model_services WHERE capability IS NULL;
-- 期望: 0

-- 检查现有数据都被标记为 chat
SELECT capability, COUNT(*) FROM user_model_services GROUP BY capability;
-- 期望: chat | N
```

- [ ] **Step 2: 为现有供应商开通 embedding 能力（如果适用）**

若当前 `model_providers` 中有支持嵌入的供应商，则自动添加 `capability='embedding'` 的记录。

```sql
INSERT INTO user_model_services (user_id, provider_id, capability, failover_order, is_enabled)
SELECT user_id, provider_id, 'embedding', 1, TRUE
FROM user_model_services
WHERE capability = 'chat'
  AND provider_id IN ('deepseek')
  AND NOT EXISTS (
    SELECT 1 FROM user_model_services AS u
    WHERE u.user_id = user_model_services.user_id
      AND u.provider_id = user_model_services.provider_id
      AND u.capability = 'embedding'
  );
```

- [ ] **Step 3: 提交**

```bash
git commit -m "chore: migrate existing user_model_services data"
```