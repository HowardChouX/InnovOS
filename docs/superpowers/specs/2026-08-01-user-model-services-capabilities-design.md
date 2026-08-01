# User Model Services — 能力感知的通配管理

## 概要

将 `user_model_services` 从单维的 供应商→用户 映射升级为 供应商+能力→用户 映射，使每个能力类型（chat / embedding / rerank / image / video）拥有独立的开通列表和故障转移顺序。

## 背景

当前 `user_model_services` 表结构：

```
user_id, provider_id, failover_order, is_enabled
PRIMARY KEY (user_id, provider_id)
```

一个用户对一个供应商只能有一条记录，无能力区分。`FailoverRouter._load_queue()` 加载时不区分能力，所有启用的供应商排成一条队列。

问题：
- 嵌入模型和聊天模型无法独立配置 failover 顺序
- 用户开通一个供应商意味着「所有能力」都可用，无法精细控制
- 无法按能力维度展示「已开通/未开通」列表

## 设计

### 数据库变更

**`user_model_services` 表** 添加 `capability` 列：

```sql
ALTER TABLE user_model_services ADD COLUMN capability TEXT NOT NULL DEFAULT 'chat';
ALTER TABLE user_model_services DROP CONSTRAINT user_model_services_pkey;
ALTER TABLE user_model_services ADD PRIMARY KEY (user_id, provider_id, capability);
```

新旧数据对比：

| 当前 | 新 |
|------|-----|
| 每条记录 = 一个供应商 | 每条记录 = 一个供应商 + 能力组合 |
| `PRIMARY KEY (user_id, provider_id)` | `PRIMARY KEY (user_id, provider_id, capability)` |
| 单 `failover_order` 全局排序 | 每能力独立 `failover_order` 排序 |

示例数据（用户 10 开通 deepseek 的聊天和嵌入 + minimax 的聊天）：

```
user_id=10, provider_id=deepseek, capability=chat,      failover_order=1, is_enabled=true
user_id=10, provider_id=deepseek, capability=embedding,  failover_order=1, is_enabled=true
user_id=10, provider_id=minimax,  capability=chat,      failover_order=2, is_enabled=true
```

**`UNIQUE (user_id, failover_order)`** 约束需改为 `UNIQUE (user_id, capability, failover_order)`，使每能力有独立的序号空间。

**索引 `ix_ums_user_enabled`** 需重建为 `(user_id, capability, is_enabled, failover_order)`，加速按能力+用户+启用的查询。

### 能力类型

| capability | 说明 | 一期实现 |
|------------|------|---------|
| `chat` | 文本对话/生成模型 | ✅ |
| `embedding` | 向量嵌入模型 | ✅ |
| `rerank` | 相关性重排模型 | ✅ |
| `image` | 图片生成模型 | ❌（预留） |
| `video` | 视频生成模型 | ❌（预留） |

### 前段 UI 变更

**`UserModelServicesPage`** 改为垂直分组布局，每个能力类型一个区块：

```
┌───────────────────────────────────────────────┐
│  用户 #10 — AI 模型服务                        │
│  ← 返回用户管理                               │
├───────────────────────────────────────────────┤
│  ┌─ 文本模型 ──────────────────────────────┐  │
│  │  已开通（拖拽调整故障转移顺序）           │  │
│  │  ⋮⋮ #1 ● deepseek / api.deepseek.com    │  │
│  │  ⋮⋮ #2 ● minimax  / api.minimaxi.com    │  │
│  │  ─────────────────────────────────────── │  │
│  │  未开通                                   │  │
│  │  ● silicon / api.siliconflow.cn  [+ 开通] │  │
│  └───────────────────────────────────────────┘  │
│  ┌─ 嵌入模型 ──────────────────────────────┐  │
│  │  已开通                                   │  │
│  │  ⋮⋮ #1 ● deepseek / api.deepseek.com    │  │
│  │  ─────────────────────────────────────── │  │
│  │  未开通                                   │  │
│  │  ● silicon / api.siliconflow.cn  [+ 开通] │  │
│  └───────────────────────────────────────────┘  │
│  ┌─ 重排模型 ──────────────────────────────┐  │
│  │  已开通: (暂未开通任何重排模型)           │  │
│  │  未开通                                   │  │
│  │  ● silicon / api.siliconflow.cn  [+ 开通] │  │
│  └───────────────────────────────────────────┘  │
│  ┌─ 图片/视频模型（预留） ────────────────┐  │
│  │  ⏳ 即将支持                             │  │
│  └───────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

每个区块独立：
- 拖拽重排（仅影响该能力的 failover 顺序）
- 开通/停用/移除按钮
- 健康状态指示器

### 后端 API 变更

**`/api/admin/users/{user_id}/model-services`** 所有端点增加 `capability` 参数：

| 端点 | 方法 | 变更 |
|------|------|------|
| `GET /model-services?capability=chat` | GET | 新增 `capability` 查询参数，过滤该能力的已开通列表 |
| `GET /model-services/available?capability=chat` | GET | 新增 `capability` 查询参数，过滤可供开通的供应商 |
| `POST /model-services` | POST | body 新增 `capability` 字段 |
| `DELETE /model-services/{provider_id}?capability=chat` | DELETE | 新增 `capability` 查询参数 |
| `POST /model-services/{provider_id}/toggle` | POST | body 新增 `capability` 字段 |
| `PUT /model-services/order` | PUT | body 新增 `capability` 字段 |

**`FailoverRouter._load_queue()`** 新增 `capability` 参数：

```python
def _load_queue(user_id: int, capability: str = "chat") -> list[dict]:
    # SQL 增加条件: AND ums.capability = %s
```

**`chat_completion()`** 的 `purpose` 参数自动映射为 `capability`：

```python
PURPOSE_TO_CAPABILITY = {
    "chat": "chat",
    "evaluation": "chat",
    "conversion": "chat",
    "extract": "chat",
    "ocr": "chat",
    "embedding": "embedding",
    "rerank": "rerank",
}
```

### 数据迁移

现有 `user_model_services` 数据（无 capability 列）全部视为 `capability='chat'`：

```sql
UPDATE user_model_services SET capability='chat' WHERE capability IS NULL;
```

这是安全的，因为当前 `FailoverRouter` 只用于 `purpose='chat'` 的调用，嵌入和重排走的是 `model_resolver` 旧路径（已废弃）。

### 未变更的部分

- `model_providers` 表 — 不变
- `api_keys` 表 — 不变
- `provider_health` 表 — 不变（健康状态按 provider 共享，不按能力区分）
- 管理员添加/编辑供应商的流程 — 不变
- 模型注册表（`model_registry.py`）— 不变

### 能力映射与 FailoverRouter

`FailoverRouter.call()` 当前接收 `purpose` 参数。改后：

```
router.call(user_id, purpose="chat", messages=...)
  → capability = PURPOSE_TO_CAPABILITY[purpose]  # "chat"
  → _load_queue(user_id, capability="chat")
  → 只遍历 chat 能力的 failover 队列
```

这样嵌入和重排的调用也会走 `FailoverRouter`，前提是用户开通了对应能力的供应商。

## 副作用与风险

- 现有 `user_model_services` 数据迁移：单次 `ALTER TABLE + UPDATE`，幂等
- `UNIQUE (user_id, failover_order)` 改为 `UNIQUE (user_id, capability, failover_order)`：需要先删旧约束再加新约束
- 前端 `UserModelServicesPage` 需要完全重写渲染逻辑
- 后端 `user_model_services` API 需要全量修改