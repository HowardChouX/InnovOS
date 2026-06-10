# InnovOS 项目重构计划

## 一、重构目标

基于思维导图，将 InnovOS 重构为符合项目标准风格的文件结构，同时整合 CherryStudio（知识库/向量检索）和 RootSeek（TRIZ 分析算法）的核心实现。

---

## 二、当前问题分析

### 2.1 Backend 问题

| 问题 | 现状 | 目标 |
|------|------|------|
| 缺少 services 层 | API 直接操作数据库 | 引入 service 层隔离业务逻辑 |
| 分析器不完整 | `algorithm/` 只有 `zr_ipm.py` | 从 RootSeek 移植完整分析器套件 |
| 知识库过于简单 | 纯文本 LIKE 搜索 | 借鉴 CherryStudio 向量检索 |
| 缺少 workflow 编排 | `workflow_service.py` 逻辑薄弱 | 引入状态机驱动的多阶段管线 |

### 2.2 Frontend 问题

| 问题 | 现状 | 目标 |
|------|------|------|
| features 目录结构扁平 | 所有功能平铺 | 按公共模块/管理员/工作流分组 |
| 多个 PlaceholderPage | `solutions`、`evaluation`、`results` | 替换为真实实现 |
| 缺少 workflow 可视化组件 | 无状态机 UI | 添加阶段进度指示器 |
| 侧边栏状态未同步 | 静态导航 | 实时反映 Agent 管线进度 |

---

## 三、重构后目录结构

### 3.1 Backend 目标结构

```
backend/app/
├── main.py                    # FastAPI 入口（不变）
├── auth.py                    # JWT 认证（不变）
├── database.py                # SQLite 连接（不变）
├── seed.py                    # 种子数据（不变）
│
├── api/                       # 路由层 — 按领域分组
│   ├── __init__.py
│   ├── auth.py                # 认证
│   ├── tasks.py               # 任务 CRUD
│   ├── knowledge.py           # 知识库
│   ├── notifications.py       # 通知系统
│   ├── patents.py             # 专利检索
│   ├── workflow.py             # 工作流
│   ├── admin/                 # 管理员路由
│   │   ├── keys.py
│   │   ├── users.py
│   │   ├── monitor.py
│   │   └── patent_db.py
│   └── workflow_steps/        # 流程步骤路由
│       ├── demand_portrait.py  # 需求洞察
│       ├── problem_modeling.py # 问题建模
│       ├── patent_search.py    # 专利检索
│       ├── solution_gen.py     # 方案生成
│       └── evaluation.py       # 方案评估
│
├── models/                    # Pydantic 模型（不变）
│
├── tables/                    # 数据库表定义（不变）
│
├── services/                  # 业务逻辑层 ← 新增
│   ├── knowledge_service.py
│   ├── notification_service.py
│   ├── patent_service.py
│   ├── workflow_service.py
│   └── history_service.py
│
├── algorithm/                 # 算法层 — 扩展
│   ├── ai_client.py           # AI 通信（现有，增强）
│   ├── key_manager.py         # Key 轮询（现有）
│   ├── crypto.py              # 加密（现有）
│   ├── base.py                # AIAnalyzer 基类 ← 从 RootSeek 移植
│   ├── analyzers/             # 领域分析器 ← 从 RootSeek 移植
│   │   ├── function_analyzer.py
│   │   ├── causal_chain.py
│   │   ├── trimming_analyzer.py
│   │   ├── sufield_analyzer.py
│   │   ├── evolution_analyzer.py
│   │   ├── ifr_generator.py
│   │   ├── resource_analyzer.py
│   │   └── thinking_tools/   # 多智能体思维工具
│   │       ├── goldfish.py
│   │       ├── nine_screens.py
│   │       └── stc_operator.py
│   ├── prompts/               # 提示词模板
│   │   ├── demand_portrait/
│   │   ├── problem_modeling/
│   │   ├── patent_search/
│   │   ├── solution_gen/
│   │   └── evaluation/
│   └── knowledge/             # 知识检索 ← 借鉴 CherryStudio
│       ├── chunker.py
│       ├── embedder.py
│       └── vector_store.py
│
└── data/                      # 静态数据（不变）
```

### 3.2 Frontend 目标结构

```
frontend/src/
├── main.tsx
├── App.tsx
│
├── api/                       # API 客户端
│   ├── client.ts              # Axios 实例 + JWT 注入
│   ├── auth.ts
│   ├── tasks.ts
│   ├── knowledge.ts
│   ├── notifications.ts
│   ├── patents.ts
│   ├── workflow.ts
│   └── admin/                 # 管理员 API
│       ├── keys.ts
│       ├── users.ts
│       ├── monitor.ts
│       └── patentDb.ts
│
├── features/                  # 功能模块
│   ├── auth/                  # 登录/注册
│   ├── dashboard/             # 首页仪表板
│   ├── knowledge/             # 知识库 ← CherryStudio 风格重构
│   │   ├── KnowledgeBasePage.tsx
│   │   ├── KnowledgeSearchPanel.tsx
│   │   └── DocumentViewer.tsx
│   ├── patents/               # 专利检索
│   ├── workflow/              # 流程步骤 ← 新增核心
│   │   ├── WorkflowPage.tsx
│   │   ├── StepIndicator.tsx
│   │   ├── DemandPortrait/
│   │   │   └── DemandPortraitPanel.tsx
│   │   ├── ProblemModeling/
│   │   │   └── ProblemModelingPanel.tsx
│   │   ├── PatentSearch/
│   │   │   └── PatentSearchStep.tsx
│   │   ├── SolutionGen/
│   │   │   └── SolutionGenPanel.tsx
│   │   └── Evaluation/
│   │       └── EvaluationPanel.tsx
│   ├── notifications/         # 通知系统
│   │   ├── NotificationBell.tsx
│   │   └── NotificationList.tsx
│   ├── history/               # 历史方案
│   │   └── HistoryPage.tsx
│   ├── patent_conversion/     # 专利转化
│   │   └── PatentConversionPage.tsx
│   └── admin/                 # 管理员模块
│       ├── KeyManagementPage.tsx
│       ├── UserManagementPage.tsx
│       ├── MonitorPage.tsx
│       └── PatentDbPage.tsx
│
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx
│   │   ├── Sidebar.tsx        # 侧边栏（增加状态机同步）
│   │   └── ProtectedRoute.tsx
│   └── ui/                    # 通用 UI 组件
│
├── store/                     # Zustand 状态管理
│   ├── useAuthStore.ts
│   ├── useWorkflowStore.ts    # 工作流状态机 ← 新增
│   ├── useNotificationStore.ts # 通知状态 ← 新增
│   └── ...
│
├── hooks/
├── types/
├── routes/
└── utils/
```

---

## 四、需从外部项目迁移/借鉴的内容

### 4.1 从 RootSeek 迁移（TRIZ 分析算法）

| 模块 | RootSeek 源路径 | InnovOS 目标路径 |
|------|----------------|-----------------|
| AI 通信基类 | `src/ai/base.py` | `algorithm/base.py` |
| 功能分析器 | `src/ai/analyzers/function_analyzer.py` | `algorithm/analyzers/function_analyzer.py` |
| 根因分析器 | `src/ai/analyzers/root_cause_analyzer.py` | `algorithm/analyzers/causal_chain.py` |
| 裁剪分析器 | `src/ai/analyzers/trimming_analyzer.py` | `algorithm/analyzers/trimming_analyzer.py` |
| 物场分析器 | `src/ai/analyzers/sufield_analyzer.py` | `algorithm/analyzers/sufield_analyzer.py` |
| 进化趋势分析器 | `src/ai/analyzers/evolution_analyzer.py` | `algorithm/analyzers/evolution_analyzer.py` |
| IFR 生成器 | `src/ai/analyzers/ifr_generator.py` | `algorithm/analyzers/ifr_generator.py` |
| 资源分析器 | `src/ai/analyzers/resource_analyzer.py` | `algorithm/analyzers/resource_analyzer.py` |
| 金鱼法 | `src/ai/analyzers/thinking_tools/` | `algorithm/analyzers/thinking_tools/` |
| 九屏幕法 | 同上 | 同上 |
| STC 算法 | 同上 | 同上 |
| 状态机 | `src/core/state_machine.py` | `algorithm/workflow_state_machine.py` |
| 提示词模板 | `src/ai/prompts/` | `algorithm/prompts/` |

**适配要点：**
- RootSeek 用 `AsyncOpenAI`，InnovOS 用 `OpenAI`（同步）→ 需改为异步调用
- RootSeek 用 `config.constants`，InnovOS 用 `algorithm.key_manager` → 替换 Key 获取逻辑
- `AIAnalyzer.__init__` 接口对齐：RootSeek 传 `AIBase`，InnovOS 传 `key_config`

### 4.2 从 CherryStudio 借鉴（知识库/向量检索）

| 功能 | CherryStudio 实现 | InnovOS 实现方案 |
|------|------------------|-----------------|
| 文档分块 | `knowledge/utils/indexing/chunk.ts` | Python 版 chunker，按段落+语义分块 |
| 向量嵌入 | `knowledge/utils/indexing/embed.ts` | 调用 BGE-M3 / 通义 Embedding API |
| 向量存储 | `knowledge/vectorstore/` (LibSQL) | SQLite + 向量扩展（或 numpy 余弦检索） |
| 知识检索 | `knowledge/utils/search.ts` | RAG 检索管线 |
| 文档读取 | `knowledge/readers/` | 支持 PDF/DOCX/TXT/MD（现有 file_parser.py） |
| Rerank | `knowledge/rerank/` | 可选：BGE-Reranker |

---

## 五、开发顺序（按优先级）

### Phase 1：基础设施重构（1-2 周）
1. Backend 引入 services 层
2. 移植 RootSeek `AIAnalyzer` 基类和 JSON 解析工具
3. 前端 features 目录重组
4. 侧边栏状态同步基础架构

### Phase 2：核心功能完善（2-3 周）
5. 需求洞察模块（RootSeek 分析器接入）
6. 问题建模模块（功能分析、因果链、矛盾分析）
7. 专利检索模块增强
8. 方案生成模块

### Phase 3：知识库升级（1-2 周）
9. 借鉴 CherryStudio 实现 RAG 检索
10. 文档向量化和分块
11. 知识库检索面板

### Phase 4：评估与辅助模块（1-2 周）
12. 方案评估引擎
13. 历史方案模块
14. 专利转化模块
15. 通知系统完善

### Phase 5：管理后台（1 周）
16. 管理员仪表板
17. 数据监控面板
18. 专利数据库管理

---

## 六、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 向量检索方案 | numpy 余弦相似度（MVP） | 避免 SQLite 向量扩展的部署复杂度，MVP 后可迁移 |
| 状态机实现 | Python Enum + 事件驱动 | 与 RootSeek `PhaseStateMachine` 一致，便于维护 |
| 异步策略 | FastAPI async + `AsyncOpenAI` | 从 RootSeek 移植时保持异步语义，提升并发性能 |
| 前端状态 | Zustand（保持现有） | 已有基础，无需引入新依赖 |
| 数据隔离 | SQLite `user_id` 字段 + 查询过滤 | 与现有架构一致，简洁有效 |
