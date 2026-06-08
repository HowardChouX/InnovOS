# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**InnovOS** (智融创新操作系统) - AI-powered innovation problem-solving system using multi-agent workflows. Built with React 19 (TypeScript) frontend and FastAPI (Python) backend. Uses SQLite for development, with PostgreSQL for production.

## Build & Development Commands

```bash
# Install dependencies
cd backend && uv sync
cd frontend && npm install

# Start development environment (both frontend and backend)
make dev

# Start individually
make backend      # FastAPI on :8000
make frontend     # Vite dev server on :5173

# Build & test
make build        # Build frontend for production
make test         # Run test suite
make lint         # Run linting (frontend: ESLint, backend: type checking)
make clean        # Remove build artifacts

# Single test
cd backend && python -m pytest tests/test_<filename>.py -v
```

## Architecture

### Frontend (React 19 + TypeScript + Vite)

```
src/
├── api/           # API 客户端（按领域拆分，JWT 自动注入）
├── pages/         # 页面组件（路由级）
├── components/    # 可复用组件
│   ├── layout/    # AppLayout, Sidebar, ProtectedRoute
│   ├── ui/        # GlassPanel, Modal, StatusBadge, EmptyState...
│   ├── dashboard/ # 首页子组件
│   ├── knowledge/ # 知识库子组件
│   └── workflow/  # 工作流可视化
├── store/         # Zustand 5 状态管理
├── types/         # TypeScript 接口
├── routes/        # React Router v7 路由配置
├── hooks/         # 自定义 React Hooks
└── utils/         # 工具函数
```

**Key Patterns:**
- 页面组件在 `pages/`，可复用子组件在 `components/<domain>/`
- State management via Zustand stores (one per feature domain)
- All API calls through `src/api/` with automatic JWT token injection
- Glass morphism UI styling with TailwindCSS 4 + CSS 变量

### Backend (FastAPI + SQLite)

```
backend/app/
├── main.py          # FastAPI 入口 + 路由挂载
├── auth.py          # JWT 认证
├── database.py      # SQLite 连接与初始化
├── seed.py          # 种子数据
├── api/             # 路由层（16 个 Router）
├── models/          # Pydantic 响应/请求模型
├── tables/          # 数据库表定义（13 张表）
├── algorithm/       # 算法层
│   ├── ai_client.py      # AI 通信客户端
│   ├── key_manager.py    # Key 轮询管理
│   ├── crypto.py         # AES 加密
│   ├── base.py           # 分析器基类
│   ├── analyzers/        # 专项分析器（需求洞察、问题建模、专利检索...）
│   ├── prompts/          # AI 提示词模板
│   ├── file_parser.py    # 文件解析器（PDF/DOCX/TXT/MD）
│   └── text_chunker.py   # 文本分块器
├── services/        # 业务逻辑层
│   ├── knowledge_service.py
│   ├── patent_conversion.py
│   └── workflow_service.py
└── data/            # 静态数据与种子
```

**Key Patterns:**
- Direct SQLite with `sqlite3.Row` for dict-like access (no ORM)
- WAL journal mode for concurrent reads
- Key Manager: API key rotation, rate limiting, concurrent request handling
- AI integration via OpenAI-compatible SDK (DeepSeek-R1, Qwen-Turbo, Qwen-Max, BGE-M3)
- 分析器继承 `AIAnalyzer` 基类，提示词模板统一管理

### Multi-Agent Architecture (ZR-MoA)

```
User Input → 知识库RAG检索 → 需求洞察Agent → 问题建模Agent
            → 专利分析Agent → 方案生成Agent → 方案评估Agent → 成果转化Agent
```

**Core Algorithm:** ZR-IPM (智融创新问题映射) - 87.4% accuracy for problem identification

**侧边栏状态机**：细粒度追踪 6-Agent 管线的子步骤进度

**Four-Dimension Evaluation Engine:**
- Innovation Assessment (patent similarity, tech evolution)
- Feasibility Assessment (constraint reasoning, rule validation)
- Completeness Assessment (reasoning chain verification, cross-validation)
- Achievement Transformation Assessment (patent applicability, industry scenario matching)

### Database Schema (13 tables in InnovOS_ACCOUNTS.db)

- `users` - 用户账户（含角色 admin/user）
- `tasks` - 创新任务
- `analyses` - 冲突分析结果（1:1 with tasks）
- `solutions` - 生成的方案
- `workflows` - 工作流状态（含 Agent 步骤 JSON）
- `patents` - 专利数据
- `evaluations` - 四维评估 + RootSeek 智枢扩展（21 列）
- `feedbacks` - 用户反馈
- `api_keys` - AES-256 加密 API 密钥
- `notifications` - 通知（含管理员撤销）
- `knowledge_docs` - 知识库文档（支持文件分块）
- `problem_modelings` - 问题建模（1:1 with tasks）
- `audit_logs` - 审计日志

### Key Configuration

Backend: `.env` (see `.env.example`)
- `INNOVOS_ENCRYPT_KEY` - Fernet encryption key
- `INNOVOS_JWT_SECRET` - JWT signing secret
- `DATABASE_URL` - SQLite path (default: InnovOS_ACCOUNTS.db)
- API Keys configured via admin UI and stored encrypted

## Development Notes

- **Type Safety:** TypeScript strict mode (frontend), Python type hints enforced (backend)
- **Commit Style:** `<type>(<scope>): <description>` (feat, fix, refactor, docs, test)
- **Branch Strategy:** main → develop → feature/fix/refactor branches
- **CORS:** Allows `localhost:5173` and `localhost:5174` (Vite dev servers)
- **JWT Tokens:** 24-hour expiry, sent via `Authorization: Bearer <token>` header
- **Database Init:** Automatic on backend startup (`init_db()` + `seed_admin_user()`)
- **Dev Servers:** Backend on `:8000`, Frontend on `:5173`

## Documentation

- `/docs/README.md` - 文档入口索引
- `/docs/RESTRUCTURE_PLAN.md` - **项目重构计划**：重构目标、目录结构、迁移方案、开发顺序
- `/docs/DEVELOPMENT_GUIDE.md` - 项目结构、数据库、API、开发规范、实施计划
- `/docs/developer/INDEX.md` - **开发文档索引**（按思维导图节点组织）
  - `00-使用指南.md` - 快速开始、功能模块概览、API 端点
  - `01-账户系统.md` - 账户类型、注册、登录、找回密码、数据隔离
  - `02-通知系统.md` - 用户接收（读取/删除）、管理员管理（发送/撤销）
  - `03-知识库.md` - 借鉴 CherryStudio 的 RAG 检索架构
  - `04-侧边栏与导航.md` - 侧边栏结构、状态同步
  - `05-需求画像.md` - RootSeek 分析器迁移（七来源/IFR/九屏幕/金鱼法/STC）
  - `06-问题建模.md` - 功能分析/因果链/矛盾/裁剪/进化趋势
  - `07-专利检索与转化.md` - 专利检索 + 查重 + 模式化
  - `08-方案生成与评估.md` - 方案生成 + 四维评估引擎
  - `09-历史方案.md` - 历史方案保存与浏览
  - `10-工作流状态机.md` - 6-Agent 管线状态机
  - `11-管理员后台.md` - Key管理/用户管理/数据监控/专利数据库管理
  - `12-API密钥管理.md` - 借鉴 CherryStudio Provider 架构的模型服务管理
- `/docs/development.md` - 代码风格和 Git 工作流
- `/docs/key-management.md` - Key 管理系统详细文档
- `/docs/ai-integration.md` - AI 接入开发文档
