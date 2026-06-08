# API 密钥与模型服务管理

> 对应思维导图节点：模型服务（参考 CherryStudio Provider 设置页面）

## 1. 概述

借鉴 CherryStudio 的 Provider（模型供应商）架构，InnovOS 将模型服务管理从简单的 Key 列表升级为完整的模型服务体系。每个供应商条目包含 API 地址、Key、模型列表、优先级和 RPM 限制，实现了供应商与 Key 池的融合。

## 2. 数据库设计

### 2.1 模型供应商表（融合 Key 池）

```sql
CREATE TABLE model_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT UNIQUE NOT NULL,      -- 'deepseek', 'openai', 'silicon'
    name TEXT NOT NULL,                    -- 显示名称
    protocol TEXT DEFAULT 'openai',        -- 'openai' | 'anthropic' | 'custom'
    api_host TEXT NOT NULL,                -- API 端点地址
    api_key_encrypted TEXT,                -- AES 加密的 API Key
    api_model TEXT DEFAULT '',             -- 默认模型
    models JSON DEFAULT '[]',             -- 支持的模型列表（JSON 数组）
    priority INTEGER DEFAULT 0,           -- 轮询优先级（越小越优先）
    max_rpm INTEGER DEFAULT 60,           -- 每分钟最大请求数
    current_rpm INTEGER DEFAULT 0,        -- 当前 RPM
    request_count INTEGER DEFAULT 0,      -- 累积请求次数
    is_enabled INTEGER DEFAULT 1,         -- 是否启用
    last_used_at TEXT,                    -- 最后使用时间
    last_reset_at TEXT,                   -- RPM 重置时间
    created_at TEXT DEFAULT (datetime('now'))
);
```

### 2.2 Key 池表（多 Key 轮询）

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT DEFAULT '',           -- 关联 model_providers.provider_id
    key_name TEXT NOT NULL,
    api_key TEXT NOT NULL,                -- AES 加密存储
    api_base_url TEXT,
    api_model TEXT DEFAULT 'deepseek-chat',
    is_active INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    max_rpm INTEGER DEFAULT 60,
    current_rpm INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    last_used_at TEXT,
    last_reset_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

> `api_keys.provider_id` 关联 `model_providers.provider_id`，支持按供应商过滤 Key 池。

## 3. 内置供应商注册表

`algorithm/providers_registry.py` 内置 7 个常用供应商：

| 供应商 | ID | API Host | 类别 |
|--------|----|----------|------|
| DeepSeek | `deepseek` | `https://api.deepseek.com` | 国内 |
| SiliconFlow | `silicon` | `https://api.siliconflow.cn` | 国内 |
| 阿里百炼 | `dashscope` | `https://dashscope.aliyuncs.com/compatible-mode/v1/` | 国内 |
| OpenAI | `openai` | `https://api.openai.com` | 国际 |
| 智谱 AI | `zhipu` | `https://open.bigmodel.cn/api/paas/v4/` | 国内 |
| Moonshot AI | `moonshot` | `https://api.moonshot.cn` | 国内 |
| Ollama | `ollama` | `http://localhost:11434` | 本地 |

每个内置供应商包含 `website`、`key_url`、`docs_url` 参考链接。

## 4. 后端服务

### 4.1 ModelService (`algorithm/model_service.py`)

```python
class ModelService:
    def list_all() -> list[dict]           # 所有已配置供应商
    def get(provider_id) -> dict | None    # 单个供应商详情
    def add(data) -> dict                  # 添加供应商
    def update(provider_id, data) -> dict  # 更新供应商
    def delete(provider_id) -> bool        # 删除供应商
    def toggle(provider_id) -> dict        # 启用/禁用切换
    async def check_connection(provider_id) -> dict  # 检查连接
    async def detect_models(provider_id, api_key_override) -> dict  # 检测模型
    def list_builtin() -> list[dict]       # 内置供应商 + 配置状态
```

### 4.2 KeyManager (`algorithm/key_manager.py`)

```python
class APIKeyManager:
    async def get_key_for_request(provider_id: str = "") -> dict  # Provider 感知轮询
    def list_keys(provider_id: str = None) -> list               # 可按 provider 过滤
    def create_key(..., provider_id: str = "") -> dict           # 创建 Key
    def update_key(key_id, **kwargs) -> dict                     # 更新 Key
    def delete_key(key_id) -> bool                               # 删除 Key
    def record_usage(key_id)                                     # 记录使用
    def mark_key_failed(key_id, error_type)                      # 标记失败
```

### 4.3 AI 客户端 (`algorithm/ai_client.py`)

```python
async def chat_completion(system_prompt, user_prompt, ..., provider_id: str = ""):
    """Provider 感知的 AI 调用"""
    key_config = await key_manager.get_key_for_request(provider_id)
    base_url = _resolve_base_url(key_config, provider_id)  # 从 model_service 解析
    client = OpenAI(api_key=key_config["api_key"], base_url=base_url)
```

解析优先级：key 自身 url → `model_service.get(provider_id).api_host` → 默认 deepseek

## 5. API 端点

### 5.1 供应商管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/admin/providers/builtin` | GET | 内置供应商列表（含配置状态） |
| `/api/admin/providers` | GET | 所有已配置供应商 |
| `/api/admin/providers` | POST | 添加/配置供应商 |
| `/api/admin/providers/{id}` | PUT | 更新供应商配置 |
| `/api/admin/providers/{id}` | DELETE | 删除供应商 |
| `/api/admin/providers/{id}/check` | POST | 检查连接 |
| `/api/admin/providers/{id}/detect-models` | POST | 检测可用模型列表 |
| `/api/admin/providers/{id}/toggle` | PUT | 启用/禁用切换 |

### 5.2 Key 池管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/admin/keys` | GET | Key 列表 |
| `/api/admin/keys` | POST | 创建 Key |
| `/api/admin/keys/{id}` | PUT | 更新 Key |
| `/api/admin/keys/{id}` | DELETE | 删除 Key |
| `/api/admin/keys/{id}/toggle` | PUT | 启用/禁用 Key |
| `/api/admin/keys/{id}/test` | POST | 测试 Key 连接 |

## 6. 前端界面

### 6.1 布局（CherryStudio 风格）

```
┌──────────────┬────────────────────────────────┐
│ 模型服务      │  DeepSeek                       │
│              │  https://api.deepseek.com        │
│ ● DeepSeek   │                                  │
│   已配置     │  API Key                         │
│   SiliconFlow│  [sk-****____________]            │
│   未配置     │  当前: sk-abc1234****             │
│   阿里百炼   │                                  │
│   未配置     │  模型 (5)              [模型检测]  │
│   OpenAI     │  ┌─────────────────────────┐    │
│   未配置     │  │ deepseek-chat        × │    │
│   + 自定义   │  │ deepseek-reasoner    × │    │
│              │  └─────────────────────────┘    │
│              │                                  │
│              │  优先级: [0]    RPM: [60]        │
│              │                                  │
│              │  [保存] [移除] [检查连接]         │
│              │                                  │
│              │  官网: deepseek.com               │
│              │  获取 Key: platform.deepseek.com  │
└──────────────┴────────────────────────────────┘
```

### 6.2 模型检测弹窗

点击「模型检测」弹出模型选择器：
- 按供应商分组（如 `deepseek-ai/`、`Qwen/`、`BAAI/`）
- 搜索框过滤
- 全选/反选分组
- 显示已选数量
- 确认按钮写入配置

## 7. 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/tables/model_providers.py` | 供应商表定义 |
| `backend/app/tables/api_keys.py` | Key 池表定义（含 provider_id） |
| `backend/app/algorithm/model_service.py` | 模型服务管理器 |
| `backend/app/algorithm/providers_registry.py` | 内置供应商注册表 |
| `backend/app/algorithm/key_manager.py` | Key 轮询管理器（Provider 感知） |
| `backend/app/algorithm/ai_client.py` | AI 客户端（Provider 路由） |
| `backend/app/algorithm/crypto.py` | AES 加密模块 |
| `backend/app/api/admin/providers.py` | 供应商管理 API |
| `backend/app/api/admin/keys.py` | Key 池管理 API |
| `frontend/src/features/admin/KeyManagementPage.tsx` | 模型服务管理页面 |
| `frontend/src/components/ui/ModelSelector.tsx` | 模型选择器弹窗组件 |
| `frontend/src/api/admin/providers.ts` | 供应商前端 API |
