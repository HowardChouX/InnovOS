# API Key 管理系统开发文档

**版本**：v1.1 | **最后更新**：2026-06-06

---

## 1. 功能概述

API Key 管理系统是 InnovOS 的核心基础设施，负责管理 AI 服务的访问凭证。支持企业级 Key 池轮询、并发控制、限流检测、自动切换和 AES-256 加密存储。

**核心能力：**

| 能力 | 说明 |
|------|------|
| Key 池管理 | 多个 API Key 统一管理，支持 CRUD |
| 加密存储 | AES-256 (Fernet) 加密，密钥通过环境变量管理 |
| 轮询调度 | 按优先级轮询使用，均衡分配请求 |
| 并发控制 | 信号量限制最大并发数（默认 5） |
| 限流检测 | 每分钟请求计数，超限自动跳过 |
| 自动切换 | Key 失效 (401/403) 自动禁用并切换 |
| 模型池 | 每个 Key 支持多个模型，调用时随机选择 |
| 权限控制 | 仅管理员可管理，普通用户不可见 |

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                     前端 (React 19)                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │          KeyManagementPage.tsx                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │ Key 列表  │  │ 创建弹窗  │  │ 获取模型列表  │  │   │
│  │  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │   │
│  │       └──────────────┼───────────────┘          │   │
│  └──────────────────────┼──────────────────────────┘   │
│                         │                                │
│              ┌──────────▼──────────┐                    │
│              │    keysApi.ts       │                    │
│              │   (CRUD + 测试)     │                    │
│              └──────────┬──────────┘                    │
└─────────────────────────┼────────────────────────────────┘
                          │ HTTP / JSON
┌─────────────────────────┼────────────────────────────────┐
│              ┌──────────▼──────────┐                    │
│              │   keys.py (Router)  │                    │
│              │   仅管理员访问       │                    │
│              └──────────┬──────────┘                    │
│                         │                                │
│              ┌──────────▼──────────┐                    │
│              │   key_manager.py    │                    │
│              │  ┌───────────────┐  │                    │
│              │  │ Key 缓存      │  │                    │
│              │  │ (30s TTL)     │  │                    │
│              │  └───────────────┘  │                    │
│              │  ┌───────────────┐  │                    │
│              │  │ 信号量 (5)    │  │                    │
│              │  └───────────────┘  │                    │
│              │  ┌───────────────┐  │                    │
│              │  │ 限流计数器    │  │                    │
│              │  └───────────────┘  │                    │
│              └──────────┬──────────┘                    │
│                         │                                │
│              ┌──────────▼──────────┐                    │
│              │    crypto.py        │                    │
│              │  AES-256 加解密     │                    │
│              └──────────┬──────────┘                    │
│                         │                                │
│              ┌──────────▼──────────┐                    │
│              │   SQLite 数据库      │                    │
│              │   api_keys 表       │                    │
│              │   (密文存储)        │                    │
│              └─────────────────────┘                    │
│                     后端 (FastAPI)                        │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 数据库设计

### 3.1 表结构

```sql
CREATE TABLE api_keys (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name         TEXT NOT NULL,                    -- Key 名称
    api_key          TEXT NOT NULL,                     -- API Key（AES-256 加密密文）
    api_base_url     TEXT DEFAULT 'https://api.deepseek.com',  -- API 基础 URL
    api_model        TEXT DEFAULT '',                   -- 模型列表（逗号分隔）
    is_active        INTEGER DEFAULT 1,                -- 是否启用
    priority         INTEGER DEFAULT 0,                -- 优先级（越小越优先）
    max_rpm          INTEGER DEFAULT 60,               -- 每分钟最大请求数
    current_rpm      INTEGER DEFAULT 0,                -- 当前分钟请求数
    last_reset_at    TEXT,                             -- 上次重置时间
    last_used_at     TEXT,                             -- 最后使用时间
    request_count    INTEGER DEFAULT 0,                -- 总使用次数
    created_at       TEXT DEFAULT (datetime('now'))    -- 创建时间
);
```

### 3.2 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键 |
| `key_name` | TEXT | - | Key 名称，用于标识 |
| `api_key` | TEXT | - | AES-256 加密密文（Fernet 格式，`gAAAAA...` 开头） |
| `api_base_url` | TEXT | `https://api.deepseek.com` | API 端点地址 |
| `api_model` | TEXT | `''` | 支持的模型，逗号分隔 |
| `is_active` | INTEGER | `1` | 启用状态（1=启用，0=禁用） |
| `priority` | INTEGER | `0` | 优先级，数字越小优先级越高 |
| `max_rpm` | INTEGER | `60` | 每分钟最大请求数 |
| `current_rpm` | INTEGER | `0` | 当前分钟已请求数 |
| `last_reset_at` | TEXT | NULL | 上次 RPM 重置时间 |
| `last_used_at` | TEXT | NULL | 最后使用时间 |
| `request_count` | INTEGER | `0` | 累计请求次数 |
| `created_at` | TEXT | `datetime('now')` | 创建时间 |

### 3.3 数据库位置

```
backend/InnovOS_ACCOUNTS.db
```

---

## 4. 后端实现

### 4.1 文件结构

```
backend/app/
├── algorithm/
│   ├── key_manager.py    # Key 管理器（轮询+并发+限流）
│   ├── ai_client.py      # AI 客户端（自动切换+重试）
│   └── crypto.py         # AES-256 加解密工具
├── api/
│   └── keys.py           # Key 管理 API（仅管理员）
└── tables/
    └── api_keys.py       # 表定义
```

### 4.2 加密模块 (`crypto.py`)

**加密算法：** AES-256 (Fernet)
**密钥来源：** 环境变量 `INNOVOS_ENCRYPT_KEY`
**依赖：** `cryptography` 库

```python
import os
from cryptography.fernet import Fernet, InvalidToken

_encrypt_key = os.getenv("INNOVOS_ENCRYPT_KEY")

if not _encrypt_key:
    raise RuntimeError(
        "未设置 INNOVOS_ENCRYPT_KEY 环境变量\n"
        "请执行: export INNOVOS_ENCRYPT_KEY=$(python -c "
        "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
    )

_fernet = Fernet(_encrypt_key.encode() if isinstance(_encrypt_key, str) else _encrypt_key)


def encrypt_key(plain_text: str) -> str:
    """加密 API Key"""
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_key(cipher_text: str) -> str:
    """解密 API Key"""
    try:
        return _fernet.decrypt(cipher_text.encode()).decode()
    except InvalidToken:
        # 兼容旧数据（未加密的 Key）
        return cipher_text
```

**加密流程：**
```
创建 Key:  明文 → encrypt_key() → 密文 → 存入数据库
读取 Key:  密文 → decrypt_key() → 明文 → 用于 AI 调用
```

**数据库存储示例：**
```
明文: sk-db9f0700db34425b804590ae3eb1cecf
密文: gAAAAABqI7u18pP-E5_O9xLBssWDC7rbzZKFuqTdmbm9lZXh5n
```

### 4.3 Key 管理器 (`key_manager.py`)

#### 核心类

```python
class APIKeyManager:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(5)  # 并发控制
        self._current_index = 0                  # 轮询索引
        self._keys_cache: list = []              # Key 缓存
        self._cache_updated_at: float = 0        # 缓存更新时间
        self._cache_ttl = 30                     # 缓存过期时间（秒）
```

#### 核心方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `acquire()` | 获取并发许可 | - |
| `release()` | 释放并发许可 | - |
| `get_key_for_request()` | 获取可用 Key | - |
| `record_usage(key_id)` | 记录使用次数 | key_id: int |
| `mark_key_failed(key_id, error_type)` | 标记 Key 失败 | key_id: int, error_type: str |
| `get_key_by_id(key_id)` | 获取单个 Key（自动解密） | key_id: int |
| `list_keys()` | 获取所有 Key | - |
| `create_key(...)` | 创建 Key（自动加密） | key_name, api_key, ... |
| `update_key(key_id, **kwargs)` | 更新 Key（api_key 自动加密） | key_id: int, **kwargs |
| `delete_key(key_id)` | 删除 Key | key_id: int |

#### 加解密集成

```python
# 创建 Key - 加密后存储
def create_key(self, key_name, api_key, ...):
    encrypted_key = encrypt_key(api_key)
    db.execute("INSERT INTO api_keys ...", (key_name, encrypted_key, ...))

# 读取 Key - 自动解密
def get_key_by_id(self, key_id):
    row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,))
    result = dict(row)
    result["api_key"] = decrypt_key(result["api_key"])
    return result

# 缓存加载 - 自动解密
def _refresh_keys_cache(self):
    for k in keys:
        d = dict(k)
        d["api_key"] = decrypt_key(d["api_key"])
        self._keys_cache.append(d)
```

#### 轮询逻辑

```python
def _get_next_key(self) -> dict:
    self._refresh_keys_cache()
    
    if not self._keys_cache:
        raise RuntimeError("未配置任何可用的API Key")
    
    key = self._keys_cache[self._current_index % len(self._keys_cache)]
    self._current_index = (self._current_index + 1) % len(self._keys_cache)
    
    return key
```

#### 限流检测

```python
def _check_rate_limit(self, key: dict) -> bool:
    db = get_db()
    
    # 每分钟重置计数
    if key.get("last_reset_at"):
        last_reset = datetime.fromisoformat(key["last_reset_at"])
        if datetime.now() - last_reset > timedelta(minutes=1):
            db.execute(
                "UPDATE api_keys SET current_rpm=0, last_reset_at=datetime('now') WHERE id=?",
                (key["id"],)
            )
            db.commit()
            key["current_rpm"] = 0
    
    # 检查是否超过限制
    if key.get("current_rpm", 0) >= key.get("max_rpm", 60):
        db.close()
        return False
    
    db.close()
    return True
```

#### 失败处理

```python
def mark_key_failed(self, key_id: int, error_type: str):
    db = get_db()
    
    if error_type in ("401", "403"):
        db.execute("UPDATE api_keys SET is_active=0 WHERE id=?", (key_id,))
    elif error_type == "429":
        db.execute("UPDATE api_keys SET current_rpm=max_rpm WHERE id=?", (key_id,))
    
    db.commit()
    db.close()
    self._cache_updated_at = 0
```

### 4.4 AI 客户端 (`ai_client.py`)

#### 模型选择

```python
def pick_model(api_model: str) -> str:
    models = [m.strip() for m in api_model.split(",") if m.strip()]
    return random.choice(models) if models else "deepseek-chat"
```

#### 带重试的 AI 调用

```python
async def chat_completion(
    system_prompt: str = "",
    user_prompt: str = "",
    temperature: float = 0.3,
    response_format: type = str,
    max_retries: int = 3,
) -> Any:
    for attempt in range(max_retries):
        await key_manager.acquire()
        try:
            key_config = await key_manager.get_key_for_request()
            
            client = OpenAI(
                api_key=key_config["api_key"],
                base_url=key_config["api_base_url"]
            )
            
            resp = client.chat.completions.create(
                model=pick_model(key_config["api_model"]),
                messages=[...],
                temperature=temperature,
            )
            
            key_manager.record_usage(key_config["id"])
            return resp.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "403" in error_msg:
                key_manager.mark_key_failed(key_config["id"], "401")
                continue
            elif "429" in error_msg:
                key_manager.mark_key_failed(key_config["id"], "429")
                await asyncio.sleep(1)
                continue
            raise
        finally:
            key_manager.release()
```

### 4.5 API 路由 (`keys.py`)

#### 请求/响应模型

```python
class CreateKeyInput(BaseModel):
    key_name: str = Field(alias="keyName")
    api_key: str = Field(alias="apiKey")
    api_base_url: str = Field(default="https://api.deepseek.com", alias="apiBaseUrl")
    api_model: str = Field(default="", alias="apiModel")
    priority: int = Field(default=0)
    max_rpm: int = Field(default=60, alias="maxRpm")

class UpdateKeyInput(BaseModel):
    key_name: Optional[str] = Field(default=None, alias="keyName")
    api_key: Optional[str] = Field(default=None, alias="apiKey")
    api_base_url: Optional[str] = Field(default=None, alias="apiBaseUrl")
    api_model: Optional[str] = Field(default=None, alias="apiModel")
    is_active: Optional[bool] = Field(default=None, alias="isActive")
    priority: Optional[int] = Field(default=None)
    max_rpm: Optional[int] = Field(default=None, alias="maxRpm")
```

#### 响应脱敏

```python
def row_to_dict(row: dict) -> dict:
    # 解密后取前缀脱敏，不暴露加密格式
    try:
        plain_key = decrypt_key(row["api_key"])
        masked = plain_key[:7] + "****" if len(plain_key) > 7 else "****"
    except Exception:
        masked = "****"
    return {
        "id": row["id"],
        "keyName": row["key_name"],
        "apiKey": masked,  # 例: sk-test****
        ...
    }
```

---

## 5. 前端实现

### 5.1 文件结构

```
frontend/src/
├── features/admin/
│   └── KeyManagementPage.tsx    # Key 管理页面
├── api/
│   └── keys.ts                  # API 调用
└── components/ui/
    └── GlassPanel.tsx           # 卡片组件（支持 style prop）
```

### 5.2 Key 管理页面

#### 页面结构

```
┌─────────────────────────────────────────────────────┐
│  API Key 管理                        [+ 添加 Key]    │
├─────────────────────────────────────────────────────┤
│  名称    │  Key         │  模型      │  RPM  │ 状态  │ 操作 │
│  DeepSeek│  sk-xxxx**** │  flash,pro │  12/60│ 启用  │ 测试 │
│  OpenAI  │  sk-yyyy**** │  gpt-4     │   0/60│ 禁用  │ 测试 │
└─────────────────────────────────────────────────────┘
```

#### 创建 Key 弹窗流程

```
1. 填写名称、API Key、API Base URL
2. 点击"获取模型列表"
   → 调用 {baseUrl}/v1/models
   → 展示模型列表（带勾选框）
3. 多选所需模型
4. 设置优先级和 RPM
5. 点击"创建" → 后端加密存储
```

#### 核心状态

```typescript
interface KeyManagementPageState {
  keys: ApiKey[];           // Key 列表
  loading: boolean;         // 加载状态
  showCreate: boolean;      // 显示创建弹窗
  models: ModelInfo[];      // 可用模型列表
  modelsLoading: boolean;   // 模型加载状态
  selectedModels: string[]; // 已选模型
  createError: string;      // 创建错误
  creating: boolean;        // 创建中
  newKey: {                 // 新 Key 数据
    keyName: string;
    apiKey: string;
    apiBaseUrl: string;
    apiModel: string;
    priority: number;
    maxRpm: number;
  };
}
```

### 5.3 API 调用层

```typescript
export const keysApi = {
  async list(): Promise<ApiKey[]> {
    const res = await apiRequest<{ data: ApiKey[] }>('/api/keys');
    return res.data;
  },

  async create(input: {
    keyName: string;
    apiKey: string;
    apiBaseUrl: string;
    apiModel: string;
    priority?: number;
    maxRpm?: number;
  }): Promise<ApiKey> {
    const res = await apiRequest<{ data: ApiKey }>('/api/keys', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async update(id: number, input: Partial<ApiKey>): Promise<ApiKey> {
    const res = await apiRequest<{ data: ApiKey }>(`/api/keys/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async delete(id: number): Promise<void> {
    await apiRequest(`/api/keys/${id}`, { method: 'DELETE' });
  },

  async test(id: number): Promise<{ message: string; response?: string }> {
    const res = await apiRequest<{ message: string; response?: string }>(
      `/api/keys/${id}/test`,
      { method: 'POST' }
    );
    return res;
  },
};
```

---

## 6. API 接口

### 6.1 获取 Key 列表

```
GET /api/keys
Authorization: Bearer <admin_token>

Response 200:
{
  "data": [
    {
      "id": 1,
      "keyName": "DeepSeek-1",
      "apiKey": "sk-xxxx****",
      "apiBaseUrl": "https://api.deepseek.com",
      "apiModel": "deepseek-v4-flash,deepseek-v4-pro",
      "isActive": true,
      "priority": 0,
      "maxRpm": 60,
      "currentRpm": 12,
      "requestCount": 156,
      "lastUsedAt": "2026-06-06T10:00:00",
      "createdAt": "2026-06-06T08:00:00"
    }
  ],
  "message": "success"
}
```

### 6.2 创建 Key

```
POST /api/keys
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "keyName": "DeepSeek-1",
  "apiKey": "sk-xxxxxxxxxxxxxxxx",
  "apiBaseUrl": "https://api.deepseek.com",
  "apiModel": "deepseek-v4-flash,deepseek-v4-pro",
  "priority": 0,
  "maxRpm": 60
}

Response 200:
{
  "data": { ... },
  "message": "创建成功"
}
```

### 6.3 更新 Key

```
PUT /api/keys/{key_id}
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "isActive": false,
  "maxRpm": 30
}

Response 200:
{
  "data": { ... },
  "message": "更新成功"
}
```

### 6.4 删除 Key

```
DELETE /api/keys/{key_id}
Authorization: Bearer <admin_token>

Response 200:
{
  "message": "删除成功"
}
```

### 6.5 测试 Key

```
POST /api/keys/{key_id}/test
Authorization: Bearer <admin_token>

Response 200:
{
  "message": "测试成功",
  "response": "连接成功"
}
```

---

## 7. 关键机制

### 7.1 Key 池轮询

```
初始化: current_index = 0
请求1: key[0 % 3] → Key A
请求2: key[1 % 3] → Key B
请求3: key[2 % 3] → Key C
请求4: key[3 % 3] → Key A (循环)
```

**优先级支持：** 查询时按 `priority ASC, id ASC` 排序，优先使用低优先级数字的 Key。

### 7.2 并发控制

```python
semaphore = asyncio.Semaphore(5)  # 最大 5 个并发请求

async def get_key_for_request():
    await semaphore.acquire()
    try:
        key = _get_next_key()
        return key
    finally:
        semaphore.release()
```

### 7.3 限流检测

```
时间线:
├── 00:00 ─── current_rpm = 0 ─── 重置
├── 00:15 ─── current_rpm = 12 ── 正常
├── 00:30 ─── current_rpm = 58 ── 接近限制
├── 00:35 ─── current_rpm = 60 ── 达到限制，跳过
├── 01:00 ─── current_rpm = 0 ─── 自动重置
```

### 7.4 自动切换

```
请求 → Key A (401) → 禁用 Key A → 切换 Key B
请求 → Key B (429) → 标记限流 → 等待 1s → 切换 Key C
请求 → Key C (200) → 成功 ✓
```

### 7.5 缓存机制

```
请求 → 检查缓存 → 缓存有效 (30s内) → 使用缓存
                → 缓存过期 → 查询数据库 → 解密 → 更新缓存
```

---

## 8. 安全机制

### 8.1 加密存储

| 层级 | 机制 | 说明 |
|------|------|------|
| 存储加密 | AES-256 Fernet | 数据库存储密文（`gAAAAA...` 开头） |
| 密钥管理 | 环境变量 | `INNOVOS_ENCRYPT_KEY`，代码中不出现 |
| 前端脱敏 | 自动截断 | 展示时 `sk-xxxx****` |
| 旧数据兼容 | 自动检测 | `decrypt_key()` 检测未加密数据直接返回原文 |

**安全模型：**

| 攻击方式 | 防护 |
|---------|------|
| 代码泄露 | 密钥不在代码中，无法解密 |
| 数据库泄露 | 无密钥无法解密 |
| 服务器被入侵 | 需要 root 权限读取环境变量 |
| 内存读取 | 需要同服务器进程注入 |

### 8.2 权限控制

- 所有 Key 管理接口需要管理员权限（`require_admin`）
- 前端侧边栏仅管理员可见 "Key管理" 入口
- 路由 `/admin/keys` 仅管理员可访问

### 8.3 传输安全

- 开发环境：HTTP（localhost）
- 生产环境：必须配置 HTTPS
- API Key 不存储在前端（仅传输）

---

## 9. 部署配置

### 9.1 默认管理员

```
用户名: InnovOS2026@admin
密码: K9#mP7$xR2!vL8
```

**注意：** 生产环境必须修改默认密码！

### 9.2 环境变量

```bash
# 加密密钥（必须配置，启动时缺失会报错）
export INNOVOS_ENCRYPT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# AI API Key（兜底，Key 池为空时使用）
DEEPSEEK_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
```

### 9.3 启动命令

```bash
# 1. 生成并设置加密密钥
export INNOVOS_ENCRYPT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. 启动后端
cd backend
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端
cd frontend
npm run dev
```

### 9.4 性能调优

| 参数 | 默认值 | 建议值 | 说明 |
|------|--------|--------|------|
| `Semaphore(5)` | 5 | 5-10 | 并发数，根据服务器性能调整 |
| `max_rpm` | 60 | 60-120 | 每 Key 每分钟请求数 |
| `_cache_ttl` | 30 | 30-60 | 缓存过期时间（秒） |

---

## 10. 扩展方向

### 10.1 已实现

- [x] Key CRUD
- [x] AES-256 加密存储
- [x] 轮询调度
- [x] 并发控制
- [x] 限流检测
- [x] 自动切换
- [x] 模型池（多模型随机选择）
- [x] 管理员权限
- [x] 前端脱敏
- [x] 获取模型列表
- [x] 测试连接

### 10.2 待实现

- [ ] 使用量统计仪表板
- [ ] 用量告警通知
- [ ] Key 自动轮换
- [ ] 多租户支持
- [ ] API Key 生成器
- [ ] 使用日志审计
- [ ] 单元测试
- [ ] HTTPS 传输加密
- [ ] PostgreSQL 数据库迁移

### 10.3 成熟度评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 核心功能 | 8/10 | CRUD、加密、轮询、限流、切换完整 |
| 安全性 | 7/10 | 加密存储+脱敏，需固定化密钥管理 |
| 可靠性 | 5/10 | 无测试、无日志审计、无告警 |
| 运维 | 3/10 | 无监控、无统计、SQLite 限制 |
| 生产就绪 | 4/10 | 需 HTTPS + PostgreSQL + 日志 + 监控 |

**适用场景：** 开发调试（2-5人）、内部演示
**不适用：** 多租户、高并发、生产环境

---

## 11. 故障排查

### 11.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 401 Unauthorized | API Key 无效 | 检查 Key 是否正确，重新添加 |
| 429 Too Many Requests | 达到限流 | 等待 1 分钟或增加 max_rpm |
| 未配置任何可用的 API Key | Key 被禁用或不存在 | 在管理页面启用/添加 Key |
| 获取模型列表失败 | Base URL 错误 | 检查 API Base URL 格式 |
| RuntimeError: 未设置 INNOVOS_ENCRYPT_KEY | 未配置加密密钥 | `export INNOVOS_ENCRYPT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")` |
| Key 解密失败 | 环境变量密钥变更 | 重新添加所有 Key |

### 11.2 调试命令

```bash
# 检查 Key 状态
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/keys

# 测试 Key 连接
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/keys/1/test

# 检查数据库（查看密文）
sqlite3 backend/InnovOS_ACCOUNTS.db "SELECT id, key_name, substr(api_key, 1, 20) || '...' as key_prefix FROM api_keys;"

# 验证加密密钥
echo $INNOVOS_ENCRYPT_KEY
```
