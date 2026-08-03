# 视频模型按用户开通管理 — 设计文档

**日期**：2026-08-03
**状态**：已批准
**范围**：视频生成接入 per-user 模型服务门控 + 前端拆分图片/视频模块

## 背景与目标

InnovOS 已有 per-user 模型服务机制（`user_model_services` 表 + 管理 API + 前端管理页），文本/嵌入/重排三类模型真正接入：用户未开通某能力的供应商时，运行时 `FailoverRouter` 拒绝该用途。但视频生成（MiniMax-H3，2026-08-02 已接入）完全绕过了这套机制——`/api/video/generate` 与后台轮询器直接 `lease_key(provider_id="minimax")`，任何登录用户都能生成，与用户开通状态无关。

**目标**：

1. 前端管理页把「图片/视频模型」预留条目拆成两个模块：`video`（激活，完整管理 UI）、`image`（保留 coming_soon，图片生成尚未实现）。
2. 视频生成真正受用户开通状态约束：未开通 → 403；已开通 → 用该用户队列第一个可用的视频供应商生成。
3. 运行时按任务记录的 provider_id 取密钥（轮询器不再硬编码 minimax）。

**非目标（明确不做）**：

- 图片生成能力（image 运行时未实现）。
- 视频供应商 failover 自动重试链（视频耗时长，跨供应商重试可能重复计费）。
- 给 `model_providers` 加 capabilities 能力标签（可用列表不过滤，与 embedding/rerank 现状一致）。
- 管理 API / 适配器 / failover_router / 数据库 schema 改动。

## 关键决策

| 决策点     | 选择                            | 理由                               |
| ---------- | ------------------------------- | ---------------------------------- |
| 运行时门控 | 按用户开通生效                  | 让管理页的开通/禁用/排序真正有意义 |
| 供应商选择 | 队列第一个可用，不自动切换      | 避免视频失败跨供应商重试重复计费   |
| 能力标签   | 不加 capabilities 列            | 与 embedding/rerank 一致，改动最小 |
| 前端拆分   | video=active, image=coming_soon | 复用现有按 capability 参数化的组件 |
| 队列读取   | 每次生成实时查库                | 管理员开关即时生效，不缓存         |

## 架构

```
管理员: 用户管理 → 模型服务 → 视频模型(active)
   └─ 给某用户开通 minimax(video) / 禁用 / 排序
                ▼
用户: 工作流视频页 → POST /api/video/generate
   ├─ 查 user_model_services(capability='video', is_enabled) 队列
   │     ├─ 空 → 403「未开通视频生成服务，请联系管理员」
   │     └─ 第一个 → lease 该 provider 的 key + api_host
   ▼
写 video_tasks(provider_id=<该provider>) → adapter.create_task → set_remote_task
                ▼
后台 video_poller: 按任务 provider_id 分组 → 每组 lease 该 provider 的 key → query_task → 回写
```

## 数据流（generate 门控）

```
POST /api/video/generate {prompt, resolution, duration, ratio}
  1. 查 user_model_services
     SELECT provider_id FROM user_model_services
     WHERE user_id=? AND capability='video' AND is_enabled=TRUE
     ORDER BY failover_order ASC LIMIT 1
     ├─ 空 → 403 {detail: "未开通视频生成服务，请联系管理员"}
     └─ provider_id 出队
  2. video_task_service.create(..., provider_id=provider_id)   // 任务行记录 provider
  3. lease_key(provider_id) + 读 model_providers.api_host
     ├─ 无密钥 → mark_failed + 400 "该视频供应商未配置密钥"
     └─ 有 → adapter.create_task → set_remote_task
  4. 返回 {taskId}
```

每次生成实时查队列，不缓存。

## 轮询器改动

`poll_once` 当前逻辑：`list_active()` → `_lease_minimax_key()`（硬编码）→ 逐个 query。

改为：

- `list_active()` 返回的任务每条带自己的 `providerId`
- 按 provider_id **分组**：`{provider_id: [task, ...]}`
- 每个组 lease 一把该 provider 的 key（无密钥 → 该组跳过，记日志，不影响其他组）
- 组内逐个 `query_task` → `apply_remote_status`

## 组件改动

### 后端

**`backend/app/api/video.py`**

- 删除 `_lease_minimax_key()`（硬编码 minimax）与 `MINIMAX_PROVIDER_ID` 常量
- 新增 `_select_user_video_provider(user_id) -> str | None`：查队列返回 provider_id，空返 None
- `generate`：先门控（None → 403）→ create(provider_id=...) → lease 该 provider key + api_host
- `api_host` 缺失时默认值删除（必须真实读库，防误用）

**`backend/app/services/video_task_service.py`**

- `create(user_id, *, prompt, resolution, duration, ratio, provider_id)`：INSERT 增加 provider_id 列

**`backend/app/services/video_poller.py`**

- 删除 `_lease_minimax_key()` 与 `MINIMAX_PROVIDER_ID`
- 新增 `_lease_key(provider_id) -> str | None`：租用指定 provider 的 key（复用 `get_api_key_service`）
- `poll_once`：按 providerId 分组 → 每组 lease → 逐个 query/回写
- 新增 `_read_api_host(provider_id) -> str`：读 model_providers.api_host

### 前端

**`backend` 无；`frontend/src/features/admin/UserModelServicesPage.tsx`**

- `CAPABILITIES`：`{key:'image', label:'图片/视频模型', coming_soon}` 拆成两条：
  - `{key:'video', label:'视频模型', description:'视频生成', status:'active'}`
  - `{key:'image', label:'图片模型', description:'图片生成（即将支持）', status:'coming_soon'}`
- 组件已按 capability 参数化，无其他改动

**`frontend/src/features/workflow/VideoDisplayPage.tsx`**

- 生成失败 403（ApiError 无 code，按 message 判断或统一提示）时展示「未开通视频生成服务，请联系管理员」提示
- 具体：`handleGenerate` 的 catch 分支对 403 显示专门提示

### 数据模型

无 schema 改动。`video_tasks.provider_id` 列已存在（Task 1 建的，`TEXT NOT NULL DEFAULT 'minimax'`），现改为显式写入。

## 错误处理

| 场景                            | 状态码 | 提示                                   |
| ------------------------------- | ------ | -------------------------------------- |
| 用户未开通 video 能力           | 403    | 未开通视频生成服务，请联系管理员       |
| 供应商已开通但无密钥            | 400    | 该视频供应商未配置密钥                 |
| 创建任务失败（401/402/429/422） | 400    | MiniMax error message（任务置 failed） |
| 轮询单组无密钥                  | —      | 记日志，跳过该组                       |

## 测试

**后端 pytest**：

- `test_video_api.py`：未开通 → 403；已开通 → 用队列第一个 provider 成功；已开通但无密钥 → 400；原 422 校验回归
- `test_video_poller.py`：多 provider 分组轮询；某 provider 无密钥只跳过该组、不影响其他组
- `test_video_task_service.py`：create 带 provider_id 参数（INSERT 含该列）
- 回归：`test_minimax_video_adapter.py`、`test_video_schema.py` 不受影响

**前端 vitest**：

- `VideoDisplayPage.test.tsx`：403 时显示未开通提示
- `UserModelServicesPage.test.tsx`：video 分类 active（加载渲染）、image 分类 coming_soon（占位）

## 部署注意

- 管理员需在 用户管理 → 模型服务 → 视频模型 为需要的用户开通 `minimax` 供应商（或保持 `user_model_services` 中该用户已有 video 行）。
- 未开通的用户生成视频将得到 403 提示，这是预期行为。
