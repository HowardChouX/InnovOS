# InnovOS AI 接入开发文档

**版本**：v1.0 | **最后更新**：2026-06-06

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 UI 层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 问题分析页   │  │ Key管理页   │  │  其他 AI 功能页      │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│              ┌─────────────────────┐                        │
│              │   API 调用层         │                        │
│              │   (fetch + JWT)     │                        │
│              └──────────┬──────────┘                        │
└─────────────────────────┼───────────────────────────────────┘
                          │ HTTP / JSON
┌─────────────────────────┼───────────────────────────────────┐
│              ┌──────────▼──────────┐                        │
│              │   路由层 (FastAPI)    │                        │
│              │   POST /api/analysis │                        │
│              │   POST /api/keys     │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│              ┌──────────▼──────────┐                        │
│              │   Key 管理器         │                        │
│              │   (轮询+并发+限流)    │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│              ┌──────────▼──────────┐                        │
│              │   AI 客户端          │                        │
│              │   (OpenAI SDK)      │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│              ┌──────────▼──────────┐                        │
│              │   ZR-IPM 算法引擎    │                        │
│              │   (问题分析+方案生成) │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │ DeepSeek│                              │
│                    │ /OpenAI │                              │
│                    └─────────┘                              │
│                      后端 (FastAPI)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. AI Key 管理系统

### 2.1 数据库表结构

```sql
CREATE TABLE api_keys (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name         TEXT NOT NULL,                    -- 名称
    api_key          TEXT NOT NULL,                     -- API Key
    api_base_url     TEXT DEFAULT 'https://api.deepseek.com',
    api_model        TEXT DEFAULT '',                   -- 模型（逗号分隔支持多模型）
    is_active        INTEGER DEFAULT 1,                -- 是否启用
    priority         INTEGER DEFAULT 0,                -- 优先级（越小越优先）
    max_rpm          INTEGER DEFAULT 60,               -- 每分钟最大请求数
    current_rpm      INTEGER DEFAULT 0,                -- 当前分钟请求数
    last_reset_at    TEXT,                             -- 上次重置时间
    last_used_at     TEXT,                             -- 最后使用时间
    request_count    INTEGER DEFAULT 0,                -- 总使用次数
    created_at       TEXT DEFAULT (datetime('now'))
);
```

### 2.2 Key 管理器 (`key_manager.py`)

**核心功能：**

| 功能 | 说明 |
|------|------|
| Key 池轮询 | 多个 Key 按优先级轮询使用 |
| 并发控制 | `asyncio.Semaphore(5)` 最大 5 并发 |
| 限流检测 | 每分钟请求计数，超过 `max_rpm` 自动跳过 |
| 自动切换 | Key 无效 (401) 自动禁用并切换下一个 |
| 缓存机制 | Key 列表缓存 30 秒，减少数据库查询 |

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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyName | string | ✅ | Key 名称 |
| apiKey | string | ✅ | API Key |
| apiBaseUrl | string | ✅ | API 基础 URL |
| apiModel | string | ✅ | 模型列表（逗号分隔） |
| priority | int | ❌ | 优先级，默认 0 |
| maxRpm | int | ❌ | 每分钟最大请求数，默认 60 |

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
        "id": "s1", "label": "能量密度", "sublabel": "(提升)",
        "type": "satellite", "color": "#60a5fa", "position": "top"
      }
    ],
    "edges": [
      { "sourceId": "center", "targetId": "s1", "label": "冲突" }
    ],
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

| 方法 | 说明 | 输入 | 输出 |
|------|------|------|------|
| `analyze()` | 问题分析 | 任务描述 | 冲突图谱 + 创新原理 |
| `generate_solutions()` | 方案生成 | 任务描述 | 创新方案列表 |
| `evaluate()` | 方案评估 | 方案描述 | 四维评分 |

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

| 机制 | 说明 |
|------|------|
| Key 加密存储 | AES-256 (Fernet) 加密，密文存入 SQLite |
| 密钥管理 | 环境变量 `INNOVOS_ENCRYPT_KEY`，代码中不出现 |
| 前端脱敏 | 展示时 Key 自动脱敏（`sk-xxxx****`） |
| 权限控制 | Key 管理接口仅管理员可访问 |
| 传输安全 | JWT Token 鉴权，生产需 HTTPS |

---

## 6. 配置说明

### 6.1 环境变量（兜底）

如果 Key 池为空，系统会尝试使用环境变量：

```bash
# .env 或系统环境变量
DEEPSEEK_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
```

### 6.2 推荐 API 提供商

| 提供商 | Base URL | 说明 |
|--------|----------|------|
| DeepSeek | `https://api.deepseek.com` | 推荐，性价比高 |
| OpenAI | `https://api.openai.com` | GPT 系列 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode` | Qwen 系列 |

### 6.3 注意事项

1. **API Key 安全**：Key 仅存储后端数据库，前端展示时脱敏（`sk-xxxx****`）
2. **并发限制**：默认最大 5 并发，可通过修改 `Semaphore(5)` 调整
3. **限流处理**：每个 Key 默认 60 RPM，超限自动切换
4. **模型池**：支持逗号分隔多个模型，调用时随机选择
5. **自动恢复**：401 的 Key 会被禁用，管理员可手动重新启用

---

## 7. 文件清单

| 文件 | 说明 |
|------|------|
| `backend/app/algorithm/key_manager.py` | Key 管理器（轮询+并发+限流） |
| `backend/app/algorithm/ai_client.py` | AI 客户端（自动切换+重试） |
| `backend/app/algorithm/zr_ipm.py` | ZR-IPM 算法引擎 |
| `backend/app/api/keys.py` | Key 管理 API |
| `backend/app/api/analysis.py` | 分析触发 API |
| `backend/app/tables/api_keys.py` | api_keys 表定义 |
| `frontend/src/features/admin/KeyManagementPage.tsx` | Key 管理页面 |
| `frontend/src/features/analysis/AnalysisPage.tsx` | 问题分析页面 |
| `frontend/src/api/keys.ts` | Key 管理 API 调用 |
| `frontend/src/api/analysis.ts` | 分析 API 调用 |
| `frontend/src/store/useAnalysisStore.ts` | 分析状态管理 |
