# InnovOS 重构文档

**版本**：v3.0 | **更新**：2026-06-07 | **依据**：功能思维导图

---

## 项目概览

```
InnovOS
├── 使用指南
├── 通知
├── 账户
└── 侧边栏
    ├── 普通用户（首页 / 知识库 / 历史方案 / 专利转化）
    └── 管理员  （+ 专利数据库管理 / 数据监控 / Key管理 / 用户管理）
```

**技术栈**：React 19 + TypeScript + Vite 8 + Zustand 5（前端）| FastAPI + SQLite（后端）

---

## 一、使用指南

### 1.1 需求

侧边栏顶部或 Header 中的「使用指南」链接 → 打开使用文档页面。

### 1.2 实现

| 项 | 文件 | 说明 |
|----|------|------|
| 新增页面 | `frontend/src/pages/GuidePage.tsx` | 静态帮助文档页，介绍 6-Agent 流程、知识库用法、专利检索、方案评估 |
| 修改路由 | `frontend/src/routes/index.tsx` | 添加 `{ path: 'guide', element: <GuidePage /> }` |
| 修改入口 | `frontend/src/components/layout/AppLayout.tsx` | Header「使用指南」span 绑定 `navigate('/guide')` |

---

## 二、通知

### 2.1 功能清单

```
通知
├── 用户接收端
│   ├── 读取 ✅ 已实现
│   └── 删除 ✅ 已实现
└── 管理员发送端
    ├── 发送 ✅ 已实现
    └── 撤销发送 ❌ 待实现
```

### 2.2 现有实现

- **后端** `backend/app/api/notifications.py`：CRUD + 批量发送 + 已读 + 清空
- **前端** `frontend/src/components/layout/AppLayout.tsx`：Header 通知下拉面板（本地 state）
- **API** `frontend/src/api/notifications.ts`：完整端点封装

### 2.3 待实现：撤销发送

| 项 | 文件 | 变更 |
|----|------|------|
| 表增加字段 | `backend/app/tables/notifications.py` | `ALTER TABLE notifications ADD COLUMN is_recalled INTEGER DEFAULT 0` |
| 新增端点 | `backend/app/api/notifications.py` | `DELETE /api/notifications/{id}/recall`（Admin，软删除设 `is_recalled=1`） |
| 修改列表查询 | `backend/app/api/notifications.py` | `list_notifications` 排除 `is_recalled=1` 的记录 |
| 新增已发列表 | `backend/app/api/notifications.py` | `GET /api/notifications/sent`（Admin，含撤销选项） |
| 前端 API | `frontend/src/api/notifications.ts` | 新增 `recall(id)` 和 `getSentNotifications()` |
| 前端 UI | `frontend/src/components/layout/AppLayout.tsx` | 通知面板增加「已发送」Tab + 每条通知的「撤销」按钮 |

---

## 三、账户

### 3.1 功能清单

```
账户
├── 类型
│   ├── 管理员 ✅（users.role = 'admin'）
│   └── 普通用户 ✅（users.role = 'user'）
├── 注册 → 手机号注册 ⏳ 暂不实现（无 SMS 服务）
├── 找回密码 → 手机号验证码找回 ⏳ 暂不实现
└── 数据绑定账户 ⏳ 待实现
```

### 3.2 账户设置（本次实现）

| 项 | 文件 | 变更 |
|----|------|------|
| 新增端点 | `backend/app/api/auth.py` | `PUT /api/auth/profile`（修改用户名） |
| 新增端点 | `backend/app/api/auth.py` | `PUT /api/auth/password`（修改密码，验证当前密码） |
| 前端 API | `frontend/src/api/auth.ts` | 新增 `updateProfile()` 和 `changePassword()` |
| 新增页面 | `frontend/src/pages/AccountSettingsPage.tsx` | 显示用户名/角色/创建时间 + 修改用户名表单 + 修改密码表单 |
| 新增路由 | `frontend/src/routes/index.tsx` | `{ path: 'account', element: <AccountSettingsPage /> }` |
| 用户菜单 | `frontend/src/components/layout/AppLayout.tsx` | 下拉菜单增加「账户设置」入口 |

### 3.3 手机号注册 / 密码找回（预留）

需要接入 SMS 服务商后再实现：
- `POST /api/auth/register-phone` — 手机号 + 验证码注册
- `POST /api/auth/send-code` — 发送短信验证码
- `POST /api/auth/reset-password` — 验证码 + 新密码重置

---

## 四、侧边栏

### 4.1 导航结构（角色区分）

```
侧边栏
├── 普通用户导航
│   ├── 首页        /
│   ├── 知识库      /knowledge
│   ├── 历史方案    /history          ← 新增
│   ├── 专利转化    /patent-conversion ← 新增
│   └── 专利检索    /patents
└── 管理员追加导航
    ├── 专利数据库管理  /admin/patents  ← 新增
    ├── 数据监控        /monitor
    ├── Key管理         /admin/keys
    └── 用户管理        /admin/users
```

### 4.2 实现

| 项 | 文件 | 变更 |
|----|------|------|
| 导航配置 | `frontend/src/utils/constants.ts` | 拆分 `USER_NAV_ITEMS` + `ADMIN_NAV_ITEMS`，删除旧 placeholder 路由 |
| 侧边栏 | `frontend/src/components/layout/Sidebar.tsx` | 按角色渲染两组导航项 |
| 路由 | `frontend/src/routes/index.tsx` | 新增 `/history`、`/patent-conversion`、`/admin/patents`；删除 `/solutions`、`/evaluation`、`/results` 占位路由 |

### 4.3 侧边栏状态机

在侧边栏中显示当前任务的分析进度（替代右侧 `AgentWorkflowPanel`）：

```
侧边栏状态机
├── 知识库分析
│   └── 知识库RAG检索 → 检索总结
├── 需求洞察
│   ├── 七维度资源分析
│   ├── IFR理想解
│   ├── 九屏幕分析
│   ├── 金鱼法
│   ├── STC算子
│   ├── 需求洞察思维工具
│   └── 目标需求（★用户打分）
├── 问题建模
│   ├── 组件超组件分析
│   ├── 因果链分析
│   ├── 功能分析
│   ├── 矛盾分析（物理矛盾→4分离原理 / 技术矛盾→40原理）
│   ├── 裁剪分析（A功能消除 / B自我功能 / C功能转移同类 / D功能转移超类）
│   ├── 进化趋势分析
│   └── 创新方向（★用户打分 + 可视化）
├── 专利检索
│   └── 检索筛选高相关度专利 → 用户★打分
├── 方案生成
│   └── 结合知识库+目标需求+创新方向+专利 → 多方案 → 用户★打分
└── 方案评估（标准）
    ├── 满足用户需求（★）
    ├── 知识库重要信息AI评分（★）
    ├── 专利评估（★）
    └── 方案生成（★）
```

| 项 | 文件 | 变更 |
|----|------|------|
| 类型定义 | `frontend/src/types/workflow.ts` | 扩展 `WORKFLOW_STEPS` 常量，增加子步骤定义 |
| Store | `frontend/src/store/useWorkflowStore.ts` | 步骤数据增加 `subSteps` 字段追踪 |
| 组件 | `frontend/src/components/layout/SidebarWorkflowProgress.tsx` | **新增**：垂直时间线，可展开/折叠子步骤，运行中脉冲动画 |
| Sidebar | `frontend/src/components/layout/Sidebar.tsx` | 导航项下方、系统状态上方插入 `<SidebarWorkflowProgress />` |
| Dashboard | `frontend/src/features/dashboard/DashboardPage.tsx` | 删除右侧 `<AgentWorkflowPanel />`，主内容区扩展为全宽 |

---

## 五、首页

### 5.1 普通用户 → 首页

```
首页
├── 中间核心内容（7 项）
│   ├── 任务输入     ✅ TaskInputPanel
│   ├── 我的任务     ✅ TaskList
│   ├── 问题分析结果  ✅ AnalysisResult（5 个 Tab）
│   ├── 知识库分析    ❌ 待实现 → KnowledgeRAGPanel
│   ├── 专利检索分析  ✅ PatentStatsPanel
│   ├── 方案生成     ✅ SolutionGeneration（评估数据待对接真实 API）
│   └── 方案评估     ❌ 待实现 → EvaluationResult
└── 侧边栏状态机    ✅ 见 4.3
```

### 5.2 待实现项

| 项 | 文件 | 变更 |
|----|------|------|
| 知识库 RAG 面板 | `frontend/src/components/dashboard/KnowledgeRAGPanel.tsx` | **新增**：显示当前任务相关的知识库检索结果，展示 9 大信息维度匹配 |
| 真实评估结果 | `frontend/src/components/dashboard/EvaluationResult.tsx` | **新增**：对接 `GET /api/evaluation/{solution_id}/latest`，替换 SolutionGeneration 中的硬编码评估卡片 |
| 管线集成 RAG | `backend/app/api/analysis.py` | Agent1 执行前先调用知识库 RAG 检索，将结果传入 AI 分析 prompt |

---

## 六、知识库

### 6.1 功能清单

```
知识库
├── 用户输入文本或导入文档
│   ├── 文本输入      ✅ 已实现
│   └── 文档导入      ❌ 待实现（PDF/DOCX/TXT/MD）
├── 呈现样式
│   └── 类似 CherryStudio 知识库  ❌ 待优化
└── AI检索识别重要信息
    └── 9 大维度结构化检索  ❌ 待实现
```

### 6.2 文档导入实现

**参考**：Cherry-Studio 知识库（`/home/chou/cherry-studio/src/main/knowledge/`）

| 项 | 文件 | 变更 |
|----|------|------|
| 文件解析器 | `backend/app/algorithm/file_parser.py` | **新增**：`parse_pdf()` (pypdf)、`parse_docx()` (python-docx)、`parse_txt()` (chardet 编码检测)、`parse_markdown()` |
| 文本分块器 | `backend/app/algorithm/text_chunker.py` | **新增**：`chunk_text(text, chunk_size=500, overlap=50)` 递归字符分割 |
| 新增依赖 | `backend/pyproject.toml` | 添加 `python-multipart`、`pypdf`、`python-docx`、`chardet` |
| 表扩展 | `backend/app/tables/knowledge.py` | 新增字段：`file_name`、`file_size`、`chunk_index`、`parent_id`、`chunk_count` |
| 上传端点 | `backend/app/api/knowledge.py` | `POST /api/knowledge/upload`（接收 UploadFile → 解析 → 分块 → 入库） |
| 分块查询 | `backend/app/api/knowledge.py` | `GET /api/knowledge/docs/{id}/chunks` |
| AI 搜索 | `backend/app/api/knowledge.py` | `POST /api/knowledge/ai-search`（AI 提取 9 维度信息） |
| 上传组件 | `frontend/src/components/ui/FileUpload.tsx` | **新增**：拖拽上传区域 + 进度条 + 文件类型过滤 |
| 上传 API | `frontend/src/api/knowledge.ts` | 新增 `uploadFile(file, metadata)` 使用 FormData + fetch |
| 页面更新 | `frontend/src/pages/KnowledgeBasePage.tsx` | 增加「导入文件」按钮 + 文件类型图标 + 分块数显示 |
| 详情页 | `frontend/src/pages/KnowledgeDetailPage.tsx` | **新增**：展示文档详情 + 分块内容列表 |
| Store | `frontend/src/store/useKnowledgeStore.ts` | **新增**：知识库状态管理（文档列表、分块、搜索） |

### 6.3 AI 重要信息维度

| 维度 | 说明 |
|------|------|
| 目标需求的运作逻辑 | 核心功能和工作原理 |
| 资源 | 可用材料、能源、信息资源 |
| 适用领域 | 技术领域和应用场景 |
| 操作指南 | 使用和操作约束 |
| 相关工程知识 | 工程参数和标准 |
| 政策 | 法规和政策约束 |
| 预算 | 成本和预算限制 |
| 参考对比产品 | 竞品和标杆产品 |
| 用户反馈 | 终端用户体验和问题 |

### 6.4 知识库检索总结

知识库检索结果作为**整个流程的参考信息**，传递给后续所有 Agent：
- Agent1（需求洞察）：参考知识库中的目标需求运作逻辑、资源、适用领域
- Agent2（问题建模）：参考工程知识、操作指南
- Agent5（专利检索）：参考相关工程知识、适用领域
- Agent3（方案生成）：综合所有维度信息
- Agent4（方案评估）：用知识库信息作为评估基准

---

## 七、历史方案

### 7.1 功能

```
历史方案 → 整个方案的生成流程
```

展示用户所有已完成的任务及其完整分析流程回溯。

### 7.2 实现

| 项 | 文件 | 变更 |
|----|------|------|
| 新增端点 | `backend/app/api/solutions.py` | `GET /api/solutions/history`（按任务分组，含工作流步骤、评估结果） |
| 新增页面 | `frontend/src/pages/HistoryPage.tsx` | 任务卡片列表 → 点击展开显示完整工作流时间线 + 方案 + 评估 |
| 新增 Store | `frontend/src/store/useHistoryStore.ts` | **新增**：历史方案数据管理 |
| 新增 API | `frontend/src/api/solutions.ts` | 新增 `getHistory()` |

---

## 八、专利转化

### 8.1 功能

```
专利转化
├── 对历史方案进行专利转化
└── 详细对比高相关度专利的详细，避免违反专利法
```

### 8.2 实现

| 项 | 文件 | 变更 |
|----|------|------|
| 新增 Router | `backend/app/api/patent_conversion.py` | **新增**：`POST /api/patent-conversion/analyze`（输入 solution_id → AI 分析侵权风险 + 规避建议） |
| 注册路由 | `backend/app/main.py` | `app.include_router(patent_conversion.router, prefix="/api/patent-conversion", tags=["patent-conversion"])` |
| 新增 API | `frontend/src/api/patentConversion.ts` | **新增**：`analyze(solutionId)` |
| 新增页面 | `frontend/src/pages/PatentConversionPage.tsx` | 选择历史方案 → 左右对比（方案 vs 相关专利）→ 侵权风险指标 → AI 规避建议 |

---

## 九、管理员模块

### 9.1 专利数据库管理

```
专利数据库管理 Admin (5 项功能)
```

| 项 | 文件 | 变更 |
|----|------|------|
| 新增端点 | `backend/app/api/patents.py` | `POST /api/patents`（创建）、`PUT /api/patents/{id}`（更新）、`DELETE /api/patents/{id}`（删除）、`POST /api/patents/import`（批量导入 JSON/CSV） |
| 新增页面 | `frontend/src/pages/PatentManagementPage.tsx` | 数据表格 + 搜索排序分页 + 新增/编辑弹窗 + 批量导入 |
| 修改 API | `frontend/src/api/patents.ts` | 新增 `createPatent()`、`updatePatent()`、`deletePatent()`、`importPatents()` |
| 新增路由 | `frontend/src/routes/index.tsx` | `{ path: 'admin/patents', element: <PatentManagementPage /> }` |

### 9.2 数据监控

```
数据监控 Admin
├── 分析任务统计    ✅ MonitorPage + TaskStatsChart
├── Apikey健康情况  ✅ KeyUsageChart
├── 系统状态统计    ✅ SystemStatus
└── 健康检查        ✅ HealthCheckPanel
```

全部已实现，无需变更。

### 9.3 Key 管理

```
Key管理 Admin → 管理员管理添加 aikey  ✅ 已实现
```

`KeyManagementPage.tsx`：完整 CRUD + 测试连接 + 模型选择。

### 9.4 用户管理

```
用户管理 Admin → 管理员管理用户账号  ✅ 已实现
```

`UserManagementPage.tsx`：列表 + 批量操作 + 发送通知 + 启用/禁用。

---

## 十、项目结构（重构后）

### 10.1 后端

```
backend/app/
├── main.py              # FastAPI 入口 + 17 个 Router 挂载
├── auth.py              # JWT 认证
├── database.py          # SQLite 连接与初始化
├── seed.py              # 种子数据
├── api/                 # 路由层
│   ├── auth.py          # /api/auth（登录/注册/Profile/密码）
│   ├── tasks.py         # /api/tasks
│   ├── analysis.py      # /api/analysis（6-Agent 管线入口）
│   ├── modeling.py      # /api/modeling
│   ├── workflow.py      # /api/workflow
│   ├── solutions.py     # /api/solutions + /history
│   ├── evaluation.py    # /api/evaluation
│   ├── feedback.py      # /api/feedback
│   ├── patents.py       # /api/patents（含 Admin CRUD）
│   ├── knowledge.py     # /api/knowledge（含文件上传 + AI 搜索）
│   ├── notifications.py # /api/notifications（含撤销）
│   ├── patent_conversion.py  # /api/patent-conversion ← 新增
│   ├── monitor.py       # /api/monitor
│   ├── keys.py          # /api/keys
│   ├── users.py         # /api/users
│   ├── principles.py    # /api/principles
│   └── sidebar.py       # /api/sidebar
├── algorithm/           # 算法层（借鉴 RootSeek 分层）
│   ├── ai_client.py     # AI 通信客户端
│   ├── key_manager.py   # Key 轮询管理
│   ├── crypto.py        # AES 加密
│   ├── base.py          # AIAnalyzer 分析器基类 ← 新增
│   ├── analyzers/       # 专项分析器 ← 新增
│   │   ├── need_analyzer.py
│   │   ├── modeling_analyzer.py
│   │   ├── patent_analyzer.py
│   │   ├── solution_analyzer.py
│   │   ├── evaluation_analyzer.py
│   │   └── thinking_tools/
│   │       ├── goldfish.py        # 金鱼法
│   │       ├── nine_screens.py    # 九屏幕分析
│   │       ├── stc_operator.py    # STC 算子
│   │       └── resource_analyzer.py # 七维度资源分析
│   ├── prompts/         # AI 提示词模板 ← 新增
│   │   ├── builder.py
│   │   ├── need_insight.py
│   │   ├── problem_modeling.py
│   │   ├── solution_gen.py
│   │   ├── evaluation.py
│   │   ├── ifr.py
│   │   ├── trimming.py
│   │   └── evolution.py
│   ├── file_parser.py   # 文件解析器（PDF/DOCX/TXT/MD）← 新增
│   └── text_chunker.py  # 文本分块器 ← 新增
├── models/              # Pydantic 模型
├── tables/              # 13 张表定义
├── services/            # 业务逻辑层 ← 新增
│   ├── knowledge_service.py
│   ├── patent_conversion.py
│   └── workflow_service.py
└── data/                # 静态数据
```

### 10.2 前端

```
frontend/src/
├── main.tsx / App.tsx / index.css
├── pages/               # 页面组件（路由级）← 重组
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── GuidePage.tsx              ← 新增
│   ├── AccountSettingsPage.tsx    ← 新增
│   ├── DashboardPage.tsx          ← 迁移自 features/
│   ├── KnowledgeBasePage.tsx      ← 迁移
│   ├── KnowledgeDetailPage.tsx    ← 新增
│   ├── PatentSearchPage.tsx       ← 迁移
│   ├── HistoryPage.tsx            ← 新增
│   ├── PatentConversionPage.tsx   ← 新增
│   ├── MonitorPage.tsx            ← 迁移
│   ├── PatentManagementPage.tsx   ← 新增
│   ├── KeyManagementPage.tsx      ← 迁移
│   └── UserManagementPage.tsx     ← 迁移
├── components/          # 可复用组件
│   ├── layout/
│   │   ├── AppLayout.tsx          ← 修改（指南链接 + 账户菜单 + 通知撤销）
│   │   ├── Sidebar.tsx            ← 修改（角色导航 + 状态机）
│   │   ├── SidebarWorkflowProgress.tsx ← 新增
│   │   └── ProtectedRoute.tsx
│   ├── ui/              # GlassPanel, Modal, StatusBadge, EmptyState, FileUpload(新增)...
│   ├── dashboard/       # TaskInput, TaskList, AnalysisResult, PatentStats,
│   │                    # SolutionGeneration, KnowledgeRAGPanel(新), EvaluationResult(新)
│   ├── knowledge/       # 知识库子组件
│   └── workflow/        # 工作流可视化
├── api/                 # API 客户端
│   ├── client.ts, auth.ts, tasks.ts, analysis.ts, workflow.ts,
│   ├── solutions.ts, evaluation.ts, feedback.ts, patents.ts,
│   ├── knowledge.ts, notifications.ts, monitor.ts, keys.ts,
│   ├── users.ts, principles.ts, sidebar.ts,
│   └── patentConversion.ts        ← 新增
├── store/               # Zustand Store
│   ├── useAuthStore, useTaskStore, useAnalysisStore, useWorkflowStore,
│   ├── useModelingStore, useSolutionStore, usePatentStore,
│   ├── useMonitorStore, useEvaluationStore, useFeedbackStore,
│   ├── useKnowledgeStore.ts       ← 新增
│   ├── useNotificationStore.ts    ← 新增（从 AppLayout 本地 state 迁移）
│   ├── useHistoryStore.ts         ← 新增
│   └── useUIStore
├── types/               # TypeScript 类型
├── hooks/               # 自定义 Hooks
├── routes/              # 路由配置
└── utils/               # 工具函数（constants, cn, formatters）
```

---

## 十一、数据库 Schema（13 张表）

见 `DEVELOPMENT_GUIDE.md` 第三章完整 DDL。关键新增字段：

| 表 | 新增字段 | 用途 |
|----|---------|------|
| `notifications` | `is_recalled INTEGER DEFAULT 0` | 管理员撤销标记 |
| `knowledge_docs` | `file_name`, `file_size`, `chunk_index`, `parent_id`, `chunk_count` | 文件上传与分块 |

---

## 十二、API 端点总览（17 个 Router）

完整端点清单见 `DEVELOPMENT_GUIDE.md` 第四章。本次新增：

| Router | 端点 | 说明 |
|--------|------|------|
| auth | `PUT /api/auth/profile` | 修改用户名 |
| auth | `PUT /api/auth/password` | 修改密码 |
| notifications | `DELETE /api/notifications/{id}/recall` | 撤销发送 |
| notifications | `GET /api/notifications/sent` | 已发送列表 |
| knowledge | `POST /api/knowledge/upload` | 文件上传导入 |
| knowledge | `GET /api/knowledge/docs/{id}/chunks` | 分块内容 |
| knowledge | `POST /api/knowledge/ai-search` | AI 结构化搜索 |
| solutions | `GET /api/solutions/history` | 历史方案汇总 |
| patent-conversion | `POST /api/patent-conversion/analyze` | 专利转化分析 |
| patents | `POST/PUT/DELETE /api/patents` | Admin CRUD |
| patents | `POST /api/patents/import` | 批量导入 |

---

## 十三、实施计划

### Phase 1：基础设施（算法层重构 + 项目结构迁移）

- [ ] 后端：创建 `algorithm/base.py` 分析器基类
- [ ] 后端：从 `zr_ipm.py` 拆分 `algorithm/analyzers/` 专项分析器
- [ ] 后端：抽取 `algorithm/prompts/` 提示词模板
- [ ] 后端：创建 `services/` 业务逻辑层
- [ ] 后端：创建 `algorithm/file_parser.py` + `text_chunker.py`
- [ ] 前端：创建 `pages/` 目录，从 `features/` 迁移页面组件
- [ ] 前端：重组 `components/dashboard/` 子组件
- [ ] 前端：删除 PlaceholderPage 和占位路由

### Phase 2：侧边栏 + 导航 + 状态机

- [ ] 前端：重构 `constants.ts`（角色导航配置）
- [ ] 前端：重构 `Sidebar.tsx`（新导航）
- [ ] 前端：新建 `SidebarWorkflowProgress.tsx`
- [ ] 前端：Dashboard 移除右侧面板，全宽布局

### Phase 3：账户 + 通知

- [ ] 后端：auth 增加 profile/password 端点
- [ ] 后端：notifications 增加 is_recalled + recall 端点
- [ ] 前端：新建 `AccountSettingsPage.tsx`
- [ ] 前端：通知面板增加撤销功能

### Phase 4：知识库增强

- [ ] 后端：knowledge_docs 表扩展字段
- [ ] 后端：文件上传 + 分块 + AI 搜索端点
- [ ] 前端：`FileUpload.tsx` + `KnowledgeDetailPage.tsx`
- [ ] 前端：`useKnowledgeStore.ts`

### Phase 5：新页面（历史方案 + 专利转化 + 专利管理）

- [ ] 后端：solutions/history 端点
- [ ] 后端：patent_conversion Router
- [ ] 后端：patents Admin CRUD
- [ ] 前端：`HistoryPage.tsx`、`PatentConversionPage.tsx`、`PatentManagementPage.tsx`

### Phase 6：Dashboard 增强

- [ ] 后端：分析管线集成知识库 RAG
- [ ] 后端：评估端点对接真实 AI
- [ ] 前端：`KnowledgeRAGPanel.tsx`、`EvaluationResult.tsx`

### Phase 7：使用指南 + 收尾

- [ ] 前端：`GuidePage.tsx`
- [ ] 更新 CLAUDE.md + docs/
- [ ] 清理废弃代码

---

## 十四、开发命令

```bash
make install   # 安装依赖
make dev       # 启动开发环境（前端 :5173 + 后端 :8000）
make build     # 生产构建
make test      # 运行测试
make lint      # 代码检查
```

## 十五、开发规范

- **提交格式**：`<type>(<scope>): <description>` — feat / fix / refactor / docs / test
- **分支策略**：main ← develop ← feature/xxx
- **前端**：函数组件 + hooks，页面放 `pages/`，子组件放 `components/<domain>/`，样式用 CSS 变量 + TailwindCSS
- **后端**：一领域一 Router，复杂逻辑放 `services/`，分析器继承 `AIAnalyzer`，提示词放 `prompts/`
- **配置**：`.env`（`INNOVOS_ENCRYPT_KEY`、`INNOVOS_JWT_SECRET`、`DATABASE_URL`）

---

**文档版本**：v3.0  
**最后更新**：2026-06-07  
**公司**：济南一竖光年人工智能科技有限公司
