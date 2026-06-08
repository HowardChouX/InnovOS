# InnovOS 开发指南

## 参考引导

**编写代码时，请参考 cherry-studio 项目的架构设计和最佳实践。**
cherry-studio 作为成熟项目，其设计模式、代码结构、数据层架构等都值得借鉴。
在实现类似功能时，优先参考其解决方案。

---

## Cherry Studio 项目结构分析

### 项目概览

**Cherry Studio** 是一个桌面端 AI 助手应用，基于 **Electron + React + TypeScript**，支持 Windows / Mac / Linux，可接入多个 LLM 提供商（OpenAI、Claude、Gemini 等）。当前处于 **v2.0.0-dev**（大重构阶段），v1 和 v2 代码共存，正在进行数据层从 Redux/Dexie 向 Cache/Preference/DataApi 架构迁移。

---

## 顶层目录布局

```
cherry-studio/
├── src/                     # 主源码（Electron 三进程架构）
├── packages/                # 内部子包（monorepo）
├── docs/                    # 项目文档（英文）
├── tests/                   # 测试基础设施 & 端到端测试
├── build/                   # 构建资源（图标、安装脚本）
├── resources/               # 运行时资源（内置agent、技能、脚本）
├── scripts/                 # 构建/CI/工具脚本（30+个）
├── config/                  # 应用升级分段配置
├── patches/                 # 依赖补丁（pnpm patches）
├── migrations/              # 数据库迁移文件
├── .github/                 # CI/CD（workflows + Issue/PR模板）
├── .claude/                 # Claude Code 配置（skills）
├── .agents/                 # Agent 技能定义
├── v2-refactor-temp/        # v2 重构临时工具（数据分类代码生成）
└── .changeset/              # 变更日志
```

---

## 核心架构：Electron 三进程模型

```
src/
├── main/          # 主进程（Node.js，Electron main）
├── preload/       # 预加载脚本（contextBridge）
├── renderer/      # 渲染进程（React UI）
└── shared/        # 共享代码（主进程 & 渲染进程都可引用）
```

### 1. `src/main/` — 主进程

| 子系统 | 路径 | 职责 |
|--------|------|------|
| **ai/** | `main/ai/` | AI 核心：provider（模型适配）、runtime（AI SDK / Claude Code）、agents（内置agent/CherryClaw）、MCP服务器、stream管理、skills、tools、observability |
| **core/** | `main/core/` | 基础设施：Application容器、lifecycle（服务生命周期）、window管理、logger、paths、job/scheduler |
| **data/** | `main/data/` | 数据层：DbService（SQLite + Drizzle）、DataApiService、PreferenceService、CacheService、BootConfigService、V2数据迁移 |
| **services/** | `main/services/` | 业务服务：文件管理、知识库、局域网传输、菜单、OCR、翻译、web搜索、代理、nutstore云存储 |
| **features/** | `main/features/` | API Gateway（Express服务器，对外暴露REST API） |
| **integration/** | `main/integration/` | 外部集成（CherryAI） |
| **knowledge/** | `main/knowledge/` | 知识库引擎：EmbedJS嵌入、reranker、预处理 |
| **utils/** | `main/utils/` | 通用工具 |

### 2. `src/renderer/` — 渲染进程（React）

| 子系统 | 路径 | 职责 |
|--------|------|------|
| **pages/** | 14个页面 | agents、home、settings、knowledge、files、history、paintings（绘图）、translate、code、notes、library、launchpad、mini-apps、openclaw |
| **components/** | 40+组件 | 通用UI组件：MarkdownEditor、ModelSelector、CodeEditor、Sidebar、VirtualList、EmojiPicker等 |
| **windows/** | 5种窗口 | main、settings、quickAssistant、selection、subWindow、migrationV2 |
| **hooks/** | 自定义hooks | agents相关、translate、通用hooks |
| **store/** | 状态管理 | V2数据hooks封装 |
| **data/** | 数据访问 | `useQuery`/`useMutation` hooks & 工具函数 |
| **services/** | 渲染端服务 | 导入、OCR |
| **i18n/** | 国际化 | 翻译文件 + i18next集成 |
| **transport/** | IPC通信 | 主进程↔渲染进程通信 |
| **context/** | React Context | 全局状态context |
| **config/** | 配置 | 模型配置、注册表 |
| **workers/** | Web Workers | 后台线程任务 |
| **assets/** | 静态资源 | 字体、图片、样式 |

### 3. `src/shared/` — 共享代码

两端（main + renderer）都可引用的代码：
- **ai/** — AI类型定义、ClaudeCode接口、tools、transport协议
- **data/** — Preference/BootConfig/Cache schema定义、DataApi schema、类型
- **types/** — 共享TypeScript类型
- **utils/** — 共享工具函数
- **command/** — 命令系统

### 4. `src/preload/` — 预加载

- `index.ts` — 主预加载脚本，通过 `contextBridge` 安全暴露API给渲染进程
- `simplest.ts` — 简化版预加载

---

## Monorepo 子包 (`packages/`)

| 包名 | 路径 | 用途 |
|------|------|------|
| **aiCore** | `packages/aiCore/` | AI核心抽象层 |
| **ai-sdk-provider** | `packages/ai-sdk-provider/` | Vercel AI SDK 的provider适配 |
| **ui** | `packages/ui/` | 共享UI组件库（Shadcn UI + Tailwind CSS） |
| **provider-registry** | `packages/provider-registry/` | LLM提供商注册表（模型列表、定价） |
| **vectorstores** | `packages/vectorstores/` | 向量数据库（libsql） |
| **mcp-trace** | `packages/mcp-trace/` | MCP调用追踪和可观测性 |
| **extension-table-plus** | `packages/extension-table-plus/` | 表格扩展组件 |

---

## 关键设计决策

1. **数据层 v2 架构**：删除 Redux/Dexie/ElectronStore，采用 `Cache / Preference / DataApi` 三层体系
   - `Cache` — 临时数据（内存/跨窗口/持久化三档）
   - `Preference` — 用户设置，跨进程自动同步
   - `DataApi` — SQLite 业务数据，Drizzle ORM

2. **生命周期系统**：`@Injectable` + `@ServicePhase` + `@DependsOn` 装饰器驱动，自动管理启动顺序和资源清理

3. **窗口管理**：`WindowManager` 支持 `default / singleton / pooled` 三种模式

4. **UI 规范**：禁止 antd/styled-components，统一用 `@cherrystudio/ui`（Tailwind + Shadcn）

5. **国际化**：`i18next`，所有用户可见字符串必须走 i18n

6. **v1/v2 共存**：v1 代码（Redux/Dexie）逐步被删除，v2 代码正在建设中

---

## 核心原则

### 编码前思考
- 明确假设，有疑问先问
- 存在多种解释时明确提出
- 更简单方案主动提出

### 简洁优先
- 最少代码解决问题
- 不添加未要求的功能
- 不为一次性代码抽象

### 精准修改
- 只改任务要求的部分
- 保持现有代码风格
- 每行改动追溯到需求

### 目标驱动
- 任务转为可验证目标
- 多步骤任务明确验证点

---

## 提交规范

Conventional Commits 格式：
- `feat:` 新功能
- `fix:` 修复bug
- `refactor:` 重构
- `docs:` 文档
- `test:` 测试
- `chore:` 构建/工具

Git 工作流：
- 使用 `git pull --rebase`
- 保持线性历史
- 提交前确保测试通过

---

## 架构设计

### 项目结构
```
InnovOS/
├── backend/    # Python FastAPI
│   ├── app/
│   │   ├── api/            # API 端点
│   │   ├── models/         # 数据模型（Pydantic）
│   │   ├── services/       # 业务服务
│   │   ├── algorithm/      # 算法实现
│   │   └── tables/         # 数据库表定义
│   └── tests/              # 测试文件
├── frontend/   # React + TypeScript + Vite
├── docs/       # 文档
└── Makefile    # 构建脚本
```

### 技术栈
- 后端：FastAPI + SQLite
- 前端：React + TypeScript + Vite
- 样式：Tailwind CSS

### 知识库架构（参考 cherry-studio）

```
API 层
  ↓
OrchestrationService（编排层）
  ↓
KnowledgeBaseService / KnowledgeItemService（数据服务层）
  ↓
Database（SQLite）
```

**关键组件：**
- `KnowledgeBaseService` — 知识库数据持久化
- `KnowledgeItemService` — 知识项数据持久化
- `KnowledgeOrchestrationService` — 工作流协调
- `KnowledgeLockManager` — 同库变更序列化

---

## 安全规范

- 不硬编码密钥密码
- 验证所有输入数据
- 使用环境变量存储配置
- 敏感数据加密存储

---

## 测试规范

### 后端
```bash
cd backend && uv run pytest
```

### 前端
```bash
cd frontend && npm test
```

---

## 调试技巧

### 后端
- API 文档：`http://localhost:8000/docs`
- 使用 Python debugger

### 前端
- 浏览器开发者工具
- React Developer Tools
