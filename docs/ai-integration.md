# InnovOS AI 接入开发文档

**版本**：v1.1 | **最后更新**：2026-06-23

---

## 1. 整体架构

当前 AI 调用链路包含以下层次（从前端请求到 AI 模型响应）：

```
前端 UI (React 19)
  → API 路由 (FastAPI, 如 /api/analysis, /api/admin/providers)
    → ModelService (model_service.py) — 3 层配置解析: 知识库级 → 系统设置 → 首个可用 Provider
      → ProviderRegistry (providers_registry.py) — 7 个内置 Provider: deepseek, silicon, dashscope, openai, zhipu, moonshot, ollama
        → KeyManager (key_manager.py) — 从 `AI_{PROVIDER_ID}_API_KEY` 环境变量读取，按 Provider 分组轮询
          → ModelRuntime (model_runtime.py) — 确保 /v1 前缀，管理超时 (30s)
            → AIClient (ai_client.py) — OpenAI SDK v2 chat_completion()
              → ZR-IPM 算法引擎 / 目标 AI 模型
```

**安全机制增强：**

- **JWT Token 版本（强制登出）**：JWT 载荷中包含 `token_version`（来自 `users.token_version` 字段，INTEGER DEFAULT 0）。每次请求时 `deps.py:get_current_user()` 比对 Token 与数据库版本，不一致则拒绝。管理员可通过 `POST /api/admin/users/{user_id}/revoke-tokens` 递增版本号，立即失效该用户所有 Token。
- **Cookie 安全加固**：JWT 通过 HttpOnly `__Host-token` cookie 传递（同时支持 `Authorization: Bearer` 头兜底）。`__Host-` 前缀确保 Cookie 仅在当前域名下设置，不可被子域名覆盖，增强 XSS 防护。
- **CI 质量门禁**：项目使用 `make quality` 作为本地 CI 门禁（ESLint → Ruff → Prettier → tsc → mypy → pytest --cov → 前端 build → bandit → npm audit），提交前必须通过。

**核心组件说明：**

| 层            | 文件                    | 职责                                                                                                      |
| ------------- | ----------------------- | --------------------------------------------------------------------------------------------------------- |
| 配置解析      | `model_service.py`      | 3 层 fallback：知识库级 → 系统设置 → 首个可用 Provider                                                    |
| Provider 注册 | `providers_registry.py` | 7 个内置 Provider 管理，按 ID 查找                                                                        |
| Key 管理      | `key_manager.py`        | 从 `AI_{PROVIDER_ID}_API_KEY` 环境变量读取 Key，按 Provider 分组，asyncio.Semaphore(5) 并发控制，RPM 限流 |
| 运行时        | `model_runtime.py`      | `ensure_v1_url()` 自动补全 /v1 路径，httpx 超时 30s                                                       |
| AI 调用       | `ai_client.py`          | OpenAI SDK v2 `chat_completion()`，重试 3 次 + 错误处理                                                   |

---

## 2. AI Key 管理系统

### 2.1 数据库表结构

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    provider_id TEXT DEFAULT '',
    key_name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    api_base_url TEXT DEFAULT 'https://api.deepseek.com',
    api_model TEXT DEFAULT 'deepseek-chat',
    is_active INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    max_rpm INTEGER DEFAULT 60,
    current_rpm INTEGER DEFAULT 0,
    last_reset_at TEXT,
    last_used_at TEXT,
    request_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
```

### 2.2 Key 管理器 (`key_manager.py`)

**核心功能：**

| 功能       | 说明                                    |
| ---------- | --------------------------------------- |
| Key 池轮询 | 多个 Key 按优先级轮询使用               |
| 并发控制   | `asyncio.Semaphore(5)` 最大 5 并发      |
| 限流检测   | 每分钟请求计数，超过 `max_rpm` 自动跳过 |
| 自动切换   | Key 无效 (401) 自动禁用并切换下一个     |
| 缓存机制   | Key 列表缓存 30 秒，减少数据库查询      |

**工作流程：**

```
请求到达 → 获取信号量 → 刷新Key缓存 → 轮询选择Key
    → 检查限流 → 调用API → 记录使用次数 → 释放信号量
         │
         ├─ 401/403 → 禁用当前Key → 重试下一个
         ├─ 429     → 标记限流 → 等待1秒 → 重试
         └─ 其他错误 → 抛出异常
```

### 2.3 模型池

每个 API Key 支持配置多个模型（逗号分隔），AI 调用时随机选择：

```python
# ai_client.py
def pick_model(api_model: str) -> str:
    """从模型池中随机选择一个模型"""
    models = [m.strip() for m in api_model.split(",") if m.strip()]
    return random.choice(models) if models else "deepseek-chat"
```

**示例：** `api_model = "deepseek-v4-flash,deepseek-v4-pro"` 会在两个模型间随机选择。

---

## 3. API 接口

### 3.1 Key 管理接口（仅管理员）

#### GET /api/keys

获取所有 API Key 列表

**请求头：** `Authorization: Bearer <admin_token>`

**响应：**

```json
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

#### POST /api/keys

创建新 API Key

**请求体：**

```json
{
  "keyName": "DeepSeek-1",
  "apiKey": "sk-xxxxxxxxxxxxxxxx",
  "apiBaseUrl": "https://api.deepseek.com",
  "apiModel": "deepseek-v4-flash,deepseek-v4-pro",
  "priority": 0,
  "maxRpm": 60
}
```

**字段说明：**

| 字段       | 类型   | 必填 | 说明                      |
| ---------- | ------ | ---- | ------------------------- |
| keyName    | string | ✅   | Key 名称                  |
| apiKey     | string | ✅   | API Key                   |
| apiBaseUrl | string | ✅   | API 基础 URL              |
| apiModel   | string | ✅   | 模型列表（逗号分隔）      |
| priority   | int    | ❌   | 优先级，默认 0            |
| maxRpm     | int    | ❌   | 每分钟最大请求数，默认 60 |

#### PUT /api/keys/{key_id}

更新 API Key

**请求体（部分更新）：**

```json
{
  "isActive": false,
  "maxRpm": 30
}
```

#### DELETE /api/keys/{key_id}

删除 API Key

#### POST /api/keys/{key_id}/test

测试 API Key 连接

**响应：**

```json
{ "message": "测试成功", "response": "连接成功" }
```

---

### 3.2 分析触发接口

#### POST /api/analysis/{task_id}/trigger

触发 AI 分析（需认证）

**流程：**

1. 验证任务存在且属于当前用户
2. 检查是否已有分析结果（有则直接返回）
3. 调用 ZR-IPM 引擎分析
4. 保存分析结果到 `analyses` 表
5. 更新任务状态

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "10",
    "taskId": "10",
    "centerNode": {
      "id": "center",
      "label": "核心冲突",
      "description": "提高能量密度 vs 保证安全性",
      "type": "center"
    },
    "satelliteNodes": [
      {
        "id": "s1",
        "label": "能量密度",
        "sublabel": "(提升)",
        "type": "satellite",
        "color": "#60a5fa",
        "position": "top"
      }
    ],
    "edges": [{ "sourceId": "center", "targetId": "s1", "label": "冲突" }],
    "principles": ["分割原理", "动态化原理", "复合材料原理"]
  },
  "message": "分析完成"
}
```

**错误响应：**

- `404` 任务不存在
- `500` AI 分析失败（Key 无效、网络错误等）

#### GET /api/analysis/{task_id}

获取已有分析结果（需认证）

---

## 4. ZR-IPM 算法引擎

### 4.1 功能

| 方法                   | 说明     | 输入     | 输出                |
| ---------------------- | -------- | -------- | ------------------- |
| `analyze()`            | 问题分析 | 任务描述 | 冲突图谱 + 创新原理 |
| `generate_solutions()` | 方案生成 | 任务描述 | 创新方案列表        |
| `evaluate()`           | 方案评估 | 方案描述 | 四维评分            |

### 4.2 Prompt 设计

**问题分析 Prompt：**

```
你是一个创新问题分析专家。分析用户的技术问题，输出JSON：
{
  "centerConflict": "核心矛盾描述",
  "satellites": [
    {"label": "方面名", "sublabel": "方向", "description": "详细描述"}
  ],
  "principles": ["推荐创新原理名"],
  "patentKeywords": ["检索关键词"]
}
```

**方案生成 Prompt：**

```
你是一个创新方案专家。返回JSON数组，每个元素包含
title, description, principles(数组), confidenceScore(0-100)
```

**方案评估 Prompt：**

```
你是一个创新评估专家。返回JSON:
scores(innovation/feasibility/completeness/conversion 0-100),
overall, grade(A+/A/B+/B/C),
strengths(数组), weaknesses(数组), recommendations(数组)
```

### 4.3 冲突图谱构建

```python
@staticmethod
def _build_conflict_graph(ai_result: dict) -> dict:
    # 卫星节点：上下左右四个方向
    colors = ["#60a5fa", "#4ade80", "#a78bfa", "#fbbf24"]
    positions = ["top", "right", "bottom", "left"]

    # 边关系：前两个为"冲突"，第三个为"关联"，第四个为"导致"
    edge_labels = ["冲突", "冲突", "关联", "导致"]
```

---

## 5. 前端集成

### 5.1 Key 管理页面

**路径：** `/admin/keys`（仅管理员可见）

**功能：**

- Key 列表展示（名称、Key、模型、RPM、状态）
- 创建 Key 弹窗（支持获取模型列表 → 多选模型）
- 启用/禁用切换
- 测试连接
- 删除 Key

**获取模型列表流程：**

```
填写 API Key + Base URL
  → 点击"获取模型列表"
  → 调用 {baseUrl}/v1/models
  → 展示模型列表（带勾选框）
  → 多选所需模型
  → 创建 Key（模型以逗号分隔存储）
```

### 5.2 问题分析页面

**路径：** `/analysis`

**功能：**

1. 选择任务（下拉框）
2. 点击"开始分析"
3. 调用 `POST /api/analysis/{taskId}/trigger`
4. 展示冲突图谱（SVG 可视化）
5. 展示创新原理（标签列表）

**Store：** `useAnalysisStore`

```typescript
interface AnalysisStore {
  analysis: ConflictAnalysis | null;
  loading: boolean;
  analyzing: boolean;
  fetchAnalysis: (taskId: string) => Promise<void>;
  triggerAnalysis: (taskId: string) => Promise<void>;
}
```

### 5.3 安全机制

| 机制         | 说明                                                            |
| ------------ | --------------------------------------------------------------- |
| API Key 来源 | 环境变量 `AI_{PROVIDER_ID}_API_KEY`，不存入数据库               |
| 密钥管理     | 环境变量管理，代码中不出现硬编码 Key                            |
| 前端脱敏     | 展示时 Key 自动脱敏（`sk-xxxx****`）                            |
| 权限控制     | Key 管理接口仅管理员可访问                                      |
| Token 版本   | JWT 内含 `token_version`，每次请求比对 DB，不一致则拒绝         |
| Cookie 安全  | HttpOnly `__Host-token` cookie + `Authorization: Bearer` 双通道 |
| 传输安全     | JWT Token 鉴权，生产需 HTTPS                                    |
| CI 门禁      | `make quality` 执行 lint + typecheck + test + build + security  |

---

## 6. 配置说明

### 6.1 环境变量（兜底）

AI 调用所需的 API Key 通过环境变量注入，KeyManager 自动扫描所有 `AI_*_API_KEY` 变量并按 Provider 分组：

```bash
# .env 或系统环境变量（支持多 Key 轮询）
AI_SILICON_API_KEY=sk-xxxxxxxx
AI_SILICON_API_KEY_1=sk-yyyyyyyy
AI_DEEPSEEK_API_KEY=sk-zzzzzzzz
```

### 6.2 推荐 API 提供商

| 提供商   | Base URL                                         | 说明           |
| -------- | ------------------------------------------------ | -------------- |
| DeepSeek | `https://api.deepseek.com`                       | 推荐，性价比高 |
| OpenAI   | `https://api.openai.com`                         | GPT 系列       |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode` | Qwen 系列      |

### 6.3 注意事项

1. **API Key 安全**：Key 来自环境变量 `AI_{PROVIDER_ID}_API_KEY`，前端展示时脱敏（`sk-xxxx****`）
2. **并发限制**：默认最大 5 并发，可通过修改 `Semaphore(5)` 调整
3. **限流处理**：每个 Key 默认 60 RPM（内存追踪），超限自动切换
4. **模型池**：ModelService 通过 3 层 fallback 解析模型配置：知识库级 → 系统设置 → 首个可用 Provider
5. **自动恢复**：401 的 Key 会被禁用，管理员可手动重新启用

---

## 7. 文件清单

| 文件                                                | 说明                                      |
| --------------------------------------------------- | ----------------------------------------- |
| `backend/app/algorithm/model_service.py`            | 模型服务（3 层配置解析）                  |
| `backend/app/algorithm/providers_registry.py`       | Provider 注册表（7 个内置 Provider）      |
| `backend/app/algorithm/key_manager.py`              | Key 管理器（环境变量扫描+轮询+并发+限流） |
| `backend/app/algorithm/model_runtime.py`            | 模型运行时（/v1 路径管理+超时）           |
| `backend/app/algorithm/ai_client.py`                | AI 客户端（OpenAI SDK v2 调用）           |
| `backend/app/algorithm/zr_ipm.py`                   | ZR-IPM 算法引擎                           |
| `backend/app/api/admin/providers.py`                | 供应商管理 API（含 Key 配置）             |
| `backend/app/api/analysis.py`                       | 分析触发 API                              |
| `backend/app/api/admin/monitor.py`                  | Key 使用统计 + 系统监控（管理员）         |
| `backend/app/tables/pg_schema.py`                   | PostgreSQL 表定义（含 api_keys、users）   |
| `frontend/src/features/admin/KeyManagementPage.tsx` | Key 管理页面                              |
| `frontend/src/features/analysis/AnalysisPage.tsx`   | 问题分析页面                              |
| `frontend/src/api/admin/providers.ts`               | 供应商 API 调用（Key/Provider）           |
| `frontend/src/api/analysis.ts`                      | 分析 API 调用                             |
| `frontend/src/store/useAnalysisStore.ts`            | 分析状态管理                              |
