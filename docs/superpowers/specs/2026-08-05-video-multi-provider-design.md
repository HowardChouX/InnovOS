# 视频生成多供应商重构 — 设计文档

**日期**：2026-08-05
**状态**：已批准
**范围**：视频生成从 MiniMax 硬编码重构为协议驱动的多供应商架构；视频模型纳入 per-user 开通管理（门控 + 动态参数 + 管理页能力展示）；接入百炼 DashScope（Wan 2.7）作为第二个视频供应商

## 背景与目标

当前视频生成（`backend/app/api/video.py`）硬编码 `MINIMAX_PROVIDER_ID`，直接 lease minimax 密钥，任何登录用户都能生成；分辨率/时长/宽高比校验规则写死 MiniMax 专属值（`768P/2K`、6 种比例）；前端 `VideoDisplayPage.tsx` 也把选项写死。2026-08-03 的用户门控设计（`2026-08-03-video-user-gating-design.md`）未落地。

**目标**：

1. 视频框架按供应商 `protocol` 字段分发（`video_minimax` → MiniMax 适配器，`video_dashscope` → 百炼 Wan 适配器），管理员建供应商时选择协议，用户无法感知/切换，未来新增供应商只需写 adapter + 注册。
2. 视频生成效力于 per-user 开通管理：未开通 → 403；开通哪个供应商就用哪个框架。
3. 分辨率/时长/宽高比等参数由 adapter 能力元数据驱动，后端动态下发，前端动态渲染，零 schema 改动。
4. 用户模型服务页视频区块激活（同文本模型），行内只读展示 adapter 能力；图片保持 coming_soon。
5. 接入百炼 Wan 2.7 系文生视频（`resolution`+`ratio` 参数模型）。

**非目标（明确不做）**：

- 图生视频、首/尾帧、全能参考、音频配音、多镜头等模式（仅文生视频）。
- wan2.6 及更早模型（`size`/`shot_type` 参数格式不兼容，不支持）。
- 管理员按用户收紧参数（只读能力展示，不做逐项开关）。
- 跨供应商 failover 自动重试（视频耗时长，跨供应商重试可能重复计费）。
- 图片生成能力（image 运行时未实现）。

## 关键决策

| 决策点       | 选择                                                     | 理由                                                                                                                                  |
| ------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 框架切换依据 | 扩展 `model_providers.protocol` 字段                     | 已验证聊天/嵌入路径不读 protocol（`failover_router` 无引用，`model_runtime` 硬编码 `"openai"`），改 protocol 不影响文本功能；零新增列 |
| 分发架构     | `VideoAdapter` 抽象基类 + 注册表（仿 `client_registry`） | 与项目既有 protocol 注册表模式一致；基类强制接口一致性                                                                                |
| 参数管理     | adapter 内置 capabilities 元数据，动态下发               | 零 schema 改动；参数永远与 adapter 实际能力一致                                                                                       |
| 生成范围     | 仅文生视频                                               | 把多供应商地基做扎实，多模态模式后续迭代                                                                                              |
| 管理页       | 视频区块激活，只读展示能力                               | 数据源与生成实际能力同源，无管理负担                                                                                                  |
| Wan 版本     | 仅 wan2.7 系（resolution+ratio）                         | 与 MiniMax H3 参数模型对齐                                                                                                            |
| 供应商选择   | 开通队列首个可用（failover_order ASC），不自动切换       | 与 08-03 门控设计一致                                                                                                                 |
| 视频区块过滤 | `capability='video'` 时只显示 `video_*` 协议供应商       | 有意偏离 08-03"不做过滤"：现在有协议字段可自然过滤，避免文本供应商误列                                                                |

## 架构

```
管理员侧:
  供应商管理 → 创建/编辑供应商行: protocol='video_minimax' | 'video_dashscope'
              api_host + api_model（如 wan2.7-t2v-2026-06-12）
  用户模型服务 → 视频模型区块（active）→ 为用户开通某供应商
              行内只读展示该 adapter 的能力（分辨率/时长/宽高比）
                    ▼
用户侧:
  VideoDisplayPage → GET /api/video/options（按开通供应商下发能力元数据）
                  → POST /api/video/generate
                    ├─ 门控: user_model_services(video, enabled) 队列首个 → provider
                    ├─ 读 model_providers.protocol → video 注册表取 adapter
                    └─ adapter.create_task → video_tasks 记录 provider_id+model
                    ▼
  后台 video_poller: 按 provider_id 分组 → 各自 protocol → adapter.query_task → 回写
```

核心原则：**`model_providers.protocol` 是唯一的框架选择依据**。

## 后端组件

### 新增 `backend/app/algorithm/clients/video_base.py` — 抽象基类 + 注册表

```python
class VideoAdapterError(Exception):
    """所有视频 adapter 的统一异常，携带归一化错误信息。"""

class VideoAdapter(ABC):
    protocol: str                # 'video_minimax' / 'video_dashscope'
    default_model: str           # api_model 为空时的回退模型名

    def capabilities(self) -> dict:
        """{resolutions: list[str], duration: {min, max}, ratios: list[str]}"""

    async def create_task(self, *, api_key, api_host, model,
                          prompt, resolution, duration, ratio) -> str:
        """创建文生视频任务，返回远端 task_id。"""

    async def query_task(self, *, api_key, api_host, remote_task_id) -> dict:
        """查询并归一化状态。返回 {status, video_url, error}，
        status ∈ pending/queued/running/succeeded/failed。"""

class VideoProtocolError(Exception):
    """protocol 未注册。"""

class VideoRegistry:
    _registry: dict[str, VideoAdapter]
    def register(adapter: VideoAdapter) -> None
    def get(protocol: str) -> VideoAdapter   # 未注册抛 VideoProtocolError
```

注册时机：`video_base.py` 底部 import 两个 adapter 模块并注册（循环 import 用局部延迟 import 规避）；`api/video.py` 与 `video_poller.py` 只需 `from app.algorithm.clients.video_base import VideoRegistry` 即可拿到已注册的 adapter。

### 重构 `backend/app/algorithm/clients/minimax_video.py`

- `MinimaxVideoAdapter` 继承 `VideoAdapter`，`protocol='video_minimax'`，`default_model='MiniMax-H3'`
- `capabilities()`：resolutions `['768P','2K']`，duration `{min:4, max:15}`，ratios `['21:9','16:9','4:3','1:1','3:4','9:16']`
- `create_task` 增加 `model` 参数（原硬编码 `DEFAULT_MODEL` 移除）
- `query_task` 归一化状态：MiniMax `succeeded`→succeeded、`failed`/`cancelled`/`expired`→failed、其余非终态→running；error 保留现有 dict→str 防御逻辑
- `MinimaxVideoError` 改为继承 `VideoAdapterError`（保留类名别名，避免测试断裂）
- 注册由 `video_base.py` 统一完成（见上），adapter 模块自身不自注册

### 新增 `backend/app/algorithm/clients/dashscope_video.py`（wan2.7 系）

- `protocol='video_dashscope'`，`default_model='wan2.7-t2v-2026-06-12'`
- `create_task`：
  - POST `{api_host}/api/v1/services/aigc/video-generation/video-synthesis`（api_host 可含或不含 `/api/v1` 后缀，拼接前做归一化）
  - header：`Authorization: Bearer {api_key}`、`X-DashScope-Async: enable`
  - body：`{"model": model, "input": {"prompt": prompt}, "parameters": {"resolution": resolution, "ratio": ratio, "duration": duration, "prompt_extend": true, "watermark": false}}`
  - 成功取 `output.task_id`
- `query_task`：GET `{api_host}/api/v1/tasks/{task_id}` → `output.task_status` 大写枚举映射：`PENDING`→queued、`RUNNING`→running、`SUCCEEDED`→succeeded（取 `output.video_url`）、其余→failed（取 `message`/`code` 为 error）
- `capabilities()`：resolutions `['480P','720P','1080P']`，duration `{min:2, max:15}`，ratios `['16:9','9:16','4:3','3:4','1:1','21:9']`
- 错误提取与 `_safe_json` 防御逻辑同 MiniMax adapter（网关 HTML 错误页容错）

### `backend/app/api/video.py` 重构

- 删除 `MINIMAX_PROVIDER_ID`、`_lease_minimax_key()`、写死的 `ALLOWED_RESOLUTIONS`/`ALLOWED_RATIOS`
- 新增 `_select_user_video_provider(user_id) -> dict | None`：
  ```sql
  SELECT ums.provider_id, mp.protocol, mp.api_host, mp.api_model
  FROM user_model_services ums JOIN model_providers mp ON mp.provider_id = ums.provider_id
  WHERE ums.user_id=? AND ums.capability='video' AND ums.is_enabled=TRUE
  ORDER BY ums.failover_order ASC LIMIT 1
  ```
- `POST /api/video/generate` 流程：门控（None→403）→ protocol 非 `video_*` → 400「该供应商不是视频模型服务」→ 注册表取 adapter（未注册→400）→ 按 `capabilities()` 校验 resolution/duration/ratio（非法→422 含允许值）→ `video_task_service.create(provider_id, model)` → lease_key（无密钥→400）→ `create_task`（model 取 `api_model` 或 `adapter.default_model`）
- `GET /api/video/options`（新）：门控同上 → 返回 `{providerId, providerName, protocol, model, capabilities}`；未开通→403
- prompt 长度上限保持 7000（Pydantic `max_length`；两个供应商都在此限制内安全）
- 每次生成实时查队列，不缓存（管理员开关即时生效）

### `backend/app/services/video_task_service.py`

- `create(user_id, *, prompt, resolution, duration, ratio, provider_id, model)`：INSERT 增加 provider_id、model 两列（列已存在）

### `backend/app/services/video_poller.py` 重构

- `poll_once`：`list_active()` → 按 `providerId` 分组 → 每组读该 provider 的 protocol/api_host + lease 一把 key → 注册表取 adapter → 组内逐个 `query_task` → `apply_remote_status`
- 某组无密钥或协议未注册 → 记日志，跳过该组，不影响其他组

### `backend/app/api/admin/user_model_services.py`

- `_load()` 响应新增 `video_capabilities` 字段：对 `video_*` 协议供应商按注册表计算 capabilities，其他能力（chat/embedding/rerank/image）为 `null`
- `_load_available()`：`capability='video'` 时 WHERE 增加 `mp.protocol LIKE 'video_%'`（其他能力不过滤，与现状一致）

### `backend/app/algorithm/model_service.py`

- `create()`：INSERT 的 `protocol` 从硬编码 `'openai'` 改为参数传入（默认 `'openai'`），白名单校验 `{openai, video_minimax, video_dashscope}`
- `update()`：增加 `protocol` 可更新字段（同样白名单校验）
- 对应 admin providers API 请求体透传 `protocol`

### 数据模型

**零 schema 改动**：

- `video_tasks.provider_id`（`TEXT NOT NULL DEFAULT 'minimax'`）、`video_tasks.model`（`TEXT NOT NULL DEFAULT 'MiniMax-H3'`）列已存在，改为显式写入
- `user_model_services` 已支持 `capability='video'`（`VALID_CAPABILITIES` 已含）
- `model_providers.protocol` 列已存在（默认 `'openai'`）

## 前端组件

### `frontend/src/api/video.ts`

- `GenerateInput`：`resolution: string; ratio: string`（去掉硬编码联合类型，值域由后端 capabilities 校验）
- 新增 `VideoCapabilities` 类型与 `VideoOptions` 类型
- 新增 `videoApi.getOptions(): Promise<Envelope<VideoOptions>>`

### `frontend/src/features/workflow/VideoDisplayPage.tsx`

- 挂载时先 `getOptions()`：
  - 403 → 显示「未开通视频生成服务，请联系管理员」，隐藏生成表单（历史列表仍显示）
  - 成功 → 用 `capabilities` 动态渲染分辨率/时长/宽高比下拉（时长按 min..max 生成序列），默认取各自第一项
- 去掉「MiniMax-H3」品牌化文案 → 「使用管理员开通的视频模型生成方案演示视频」
- 保留现有 5s 轮询与历史列表逻辑

### `frontend/src/features/admin/UserModelServicesPage.tsx`

- `CAPABILITIES` 拆分：
  - `{key:'video', label:'视频模型', description:'视频生成', status:'active'}`
  - `{key:'image', label:'图片模型', description:'图片生成（即将支持）', status:'coming_soon'}`
- 视频区块已开通行下方只读展示 `video_capabilities`（分辨率档位、时长范围、宽高比列表）

### `frontend/src/features/admin/ModelServiceForm.tsx`

- 新增「协议」下拉：`openai（文本/通用）` / `video_minimax（MiniMax 视频）` / `video_dashscope（百炼 Wan 视频）`，创建与编辑均可设置
- `frontend/src/api/admin/userModelServices.ts`：`UserModelService` 增加 `video_capabilities?: VideoCapabilities | null`

## 错误处理

| 场景                                        | 状态码 | 提示                                          |
| ------------------------------------------- | ------ | --------------------------------------------- |
| 用户未开通 video 能力（generate / options） | 403    | 未开通视频生成服务，请联系管理员              |
| 开通的供应商 protocol 非 `video_*`          | 400    | 该供应商不是视频模型服务，请联系管理员        |
| 协议未在注册表注册                          | 400    | 不支持的视频协议: {protocol}（任务置 failed） |
| 供应商无密钥                                | 400    | 该视频供应商未配置密钥（任务置 failed）       |
| 参数超出 capabilities                       | 422    | 非法分辨率/时长/宽高比（提示允许值）          |
| adapter 创建任务失败                        | 400    | adapter 归一化错误信息（任务置 failed）       |
| prompt 超 7000 字符                         | 422    | Pydantic 校验                                 |
| 轮询某组无密钥/协议未注册                   | —      | 记日志，跳过该组，不影响其他组                |

## 测试

**后端 pytest**：

- `test_video_base.py`（新）：注册表 get 未知协议抛 `VideoProtocolError`；两个 adapter capabilities 结构断言
- `test_minimax_video_adapter.py`（改造）：适配基类接口；状态归一化（cancelled→failed、expired→failed）
- `test_dashscope_video_adapter.py`（新）：create 请求体结构（`X-DashScope-Async` header、input/parameters 分层、model 传参）；query 状态映射 PENDING/RUNNING/SUCCEEDED/FAILED；video_url 提取；网关 HTML 错误体容错
- `test_video_api.py`：未开通→403（generate 与 options）；minimax/dashscope 两条协议路径（mock adapter）；按 capabilities 校验→422；非视频协议→400；options 返回 capabilities 结构
- `test_video_poller.py`：混合协议分组轮询；缺密钥/未知协议只跳过该组、不影响其他组
- `test_video_task_service.py`：create 带 provider_id + model（INSERT 含两列）
- admin user*model_services 测试：video capability 的 available 只含 `video*\*` 协议供应商；list 响应含 video_capabilities

**前端 vitest**：

- `VideoDisplayPage.test.tsx`：403 → 未开通提示且表单隐藏；按 capabilities 渲染下拉选项
- `UserModelServicesPage.test.tsx`：video 区块 active + 能力展示；image 仍 coming_soon
- `ModelServiceForm.test.tsx`：protocol 下拉渲染与提交

## 部署注意

1. **无 DB 迁移**。现有 minimax 供应商行：把 protocol 更新为 `video_minimax`（供应商表单下拉或一次性 UPDATE）。聊天功能不受影响（聊天路径不读 protocol）。
2. 新增百炼供应商行：protocol=`video_dashscope`，api_host 填实际工作空间端点（`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1` 或公共 `https://dashscope.aliyuncs.com/api/v1`），api_model 填 `wan2.7-t2v-2026-06-12`，配 DashScope key。adapter 只拼接路径，端点完全由管理员配置。
3. 管理员在 用户管理 → 模型服务 → 视频模型 为用户开通视频供应商。
4. 同一供应商可同时供文本聊天和视频：同一行即可，protocol=video_minimax 不影响聊天路径。
