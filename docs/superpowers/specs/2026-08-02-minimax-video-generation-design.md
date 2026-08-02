# MiniMax 视频生成集成 — 设计文档

**日期**：2026-08-02
**状态**：已批准
**范围**：第一期 — 仅文生视频（t2va）

## 背景与目标

InnovOS 工作流第 7 阶段「方案视频化展示」目前是纯前端 Mock（`VideoDisplayMockPage.tsx`，硬编码假数据 + 手写假播放器）。本设计将其替换为真正可工作的视频生成能力，接入 MiniMax 视频生成 V2 API（模型 `MiniMax-H3`，海螺 03）。

**目标**：用户在工作流视频阶段输入文本 prompt，系统异步调用 MiniMax 生成视频，生成完成后可在页面内播放；任务持久化，用户离开页面后后台仍继续推进，历史列表可查看过往生成记录。

**非目标（后续迭代）**：图生视频（i2va）、多模态参考生视频（r2va）、文件上传基础设施、视频生成与工作流方案输出的自动联动。

## 关键决策

| 决策点      | 选择                           | 理由                                             |
| ----------- | ------------------------------ | ------------------------------------------------ |
| 生成场景    | 仅文生视频（t2va）             | 无需文件上传，先跑通全链路                       |
| 前端        | 替换现有 Mock 页，不新建独立页 | 复用工作流阶段入口                               |
| 任务管理    | 持久化 + 历史列表              | 视频生成耗时长，需可追溯                         |
| 轮询驱动    | 独立后台轮询器（方案 B）       | 用户离开页面任务仍推进，不耦合知识库作业系统     |
| prompt 来源 | 用户手动输入                   | 与方案输出解耦，简单直接                         |
| 播放器      | 原生 `<video controls>`        | MiniMax 返回公网 URL，原生控件自带倍速/音量/全屏 |

## 架构

```
前端 VideoDisplayPage（路由 workflow/video 不变）
   │ POST /api/video/generate {prompt, resolution, duration, ratio}
   ▼
api/video.py ──► 写 video_tasks (status=pending)
   │            └► MinimaxVideoAdapter.create_task() → remote_task_id
   │            └► 回填 remote_task_id, status=queued
   ▼
返回 {taskId}（立即返回，不等待生成）

后台 video_poller（main.py startup 启动的 asyncio 循环，每 5s 一轮）
   │ SELECT status IN (pending,queued,running) 的任务
   │ → adapter.query_task() → 更新 status/video_url/error
   ▼
前端每 5s 轮询 GET /api/video/tasks，看到状态推进 → succeeded 时播放
```

## 数据模型

新增 `video_tasks` 表，加入 `backend/app/tables/pg_schema.py`，随 `init_db()` 幂等创建（`CREATE TABLE IF NOT EXISTS`）。

```sql
CREATE TABLE IF NOT EXISTS video_tasks (
    id              TEXT PRIMARY KEY,              -- uuid
    user_id         TEXT NOT NULL,                 -- 归属 users.id
    provider_id     TEXT NOT NULL DEFAULT 'minimax',
    model           TEXT NOT NULL DEFAULT 'MiniMax-H3',
    prompt          TEXT NOT NULL,
    resolution      TEXT NOT NULL DEFAULT '768P',  -- 768P / 2K
    duration        INTEGER NOT NULL DEFAULT 5,    -- 4~15
    ratio           TEXT NOT NULL DEFAULT '16:9',
    remote_task_id  TEXT,                          -- MiniMax 侧 task_id
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending/queued/running/succeeded/failed/expired
    video_url       TEXT,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_video_tasks_user   ON video_tasks(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_video_tasks_status ON video_tasks(status);
```

## 后端组件

### MiniMax 适配器 — `backend/app/algorithm/clients/minimax_video.py`

用 httpx 直打 REST（不走 OpenAI SDK，MiniMax 非 OpenAI 协议）。实例不持有 api_key，每次调用传入。

- `create_task(api_key, *, prompt, resolution, duration, ratio) -> str`
  - `POST {api_host}/v2/video_generation`
  - body: `{model: "MiniMax-H3", content: [{type: "text", text: prompt}], resolution, duration, ratio}`
  - 返回响应中的 `task_id`
  - 非 2xx 抛出携带 MiniMax error message 的异常
- `query_task(api_key, api_host, remote_task_id) -> dict`
  - 查询任务状态，返回 `{status, video_url, error}`
  - **前置项**：查询接口的确切路径与响应结构需在实现前从 MiniMax 文档索引（`https://platform.minimaxi.com/docs/llms.txt` 中的 `video-generation-v2-query` 页）确认，不靠猜测。

### 供应商注册

`model_providers` 插入一条记录：

- `provider_id='minimax'`
- `protocol='minimax-video'`
- `api_host='https://api.minimaxi.com'`
- `api_model='MiniMax-H3'`

密钥经现有 `ApiKeyService` 加密存入 `api_keys`，适配器通过现有 lease 机制取明文。可在模型管理页配置密钥。

### API 路由 — `backend/app/api/video.py`

`prefix=/api/video`，全部走 `get_current_user` 鉴权。

| 方法     | 路径                    | 作用                                                                                                       |
| -------- | ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| `POST`   | `/api/video/generate`   | 校验参数 → 写 video_tasks(pending) → adapter.create_task() → 回填 remote_task_id(queued) → 返回 `{taskId}` |
| `GET`    | `/api/video/tasks`      | 当前用户任务列表（创建时间倒序）                                                                           |
| `GET`    | `/api/video/tasks/{id}` | 单任务详情（校验归属）                                                                                     |
| `DELETE` | `/api/video/tasks/{id}` | 删除本地任务记录（不撤销远端）                                                                             |

**参数校验**（非法返回 422）：

- `prompt`：非空，≤ 7000 字符
- `duration`：整数，∈ [4, 15]
- `resolution`：∈ {`768P`, `2K`}
- `ratio`：∈ {`21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`}（t2va 必填且不能 adaptive）

### 后台轮询器 — `backend/app/services/video_poller.py`

- `main.py` startup 启动 asyncio 循环，shutdown 通过 `asyncio.Event` 停止
- 每 5s 一轮：`SELECT` 所有 `status IN (pending,queued,running)` 任务 → 逐个 `adapter.query_task()` → 更新 `status/video_url/error/updated_at`
- 单任务查询异常只记日志、跳过，不影响其他任务
- 终态兜底：MiniMax 侧 `failed/expired` 同步到本地终态
- 所有 DB 操作用 `with db_session()` 保证连接归还

### 错误处理

- 创建任务失败（401 鉴权 / 402 余额 / 429 限流 / 422 敏感内容）→ 任务行置 `failed`，`error` 存 MiniMax message
- 密钥未配置 → `generate` 返回明确错误「未配置 MiniMax 密钥」
- 查询返回 `failed/expired` → 同步本地终态

## 前端组件

### 替换策略

路由 `workflow/video` 不变。删除 Mock 遗产：

- `MOCK_VIDEOS` 硬编码数组
- 手写假控制栏（倍速/音量/画中画）
- 硬编码散热可视化
- 孤儿组件 `VideoDisplayView.tsx`（未被引用）

### 页面结构（自上而下）

1. **生成表单**（新增）
   - prompt textarea（必填，≤ 7000 字符）
   - 参数选择：分辨率（768P/2K）、时长（4–15s）、宽高比（白名单 6 种）
   - 「生成视频」按钮 → `POST /api/video/generate`，提交后列表顶部出现 pending 任务

2. **主播放区**（替换假播放器）
   - 选中 succeeded 任务 → 原生 `<video controls src={video_url}>`
   - 选中 running/queued/pending → 生成中状态（转圈 + 状态文字 + 已等待时长）
   - 选中 failed/expired → 错误信息
   - 未选中 → 空状态提示

3. **历史列表**（替换 MOCK_VIDEOS）
   - 数据来自 `GET /api/video/tasks`
   - 每行：prompt 摘要、参数、状态徽章、创建时间
   - 点击选中 → 主播放区联动
   - 轮询：挂载后每 5s 调 `GET /api/video/tasks`，直到无未终态任务则停止

**状态徽章映射**：`pending/queued/running` → 生成中（蓝）、`succeeded` → 已生成（绿）、`failed/expired` → 失败（红）

### 新增前端文件

- `src/api/video.ts` — API 客户端（generate / listTasks / getTask / deleteTask），走现有 `client.ts` JWT 注入

## 测试

**后端（pytest）**：

- 适配器：mock httpx，验证 create/query 请求体与响应解析
- API：参数校验（非法 duration/ratio → 422）、鉴权、任务创建、归属隔离
- 轮询器：mock adapter，验证状态推进（running → succeeded 写入 video_url）

**前端（vitest）**：

- mock `api/video.ts`，验证表单提交、列表渲染、状态徽章、轮询启停

## 实现前置项

写适配器前需从 MiniMax 文档确认查询接口（`video-generation-v2-query`）的确切路径与响应结构。抓取入口：`https://platform.minimaxi.com/docs/llms.txt`。若抓取失败需回报。
