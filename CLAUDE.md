# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**InnovOS** (智融创新操作系统) — AI-powered innovation problem-solving system using multi-agent workflows. Built with React 19 (TypeScript) frontend and FastAPI (Python 3.11+) backend. PostgreSQL only (pgvector for embeddings).

## Build & Development Commands

```bash
# Install dependencies
cd backend && uv sync
cd frontend && npm install

# Start development (both frontend and backend)
make dev

# Start individually
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev

# Build & test
make build        # Frontend production build with code splitting
make test         # Run all tests (backend + frontend)
make lint         # Run linting (ESLint, Ruff, mypy)
make format       # Auto-format code (Prettier, Black, isort, Ruff)
make clean        # Remove build artifacts
make security     # Bandit + safety dependency scan
make docker-build # Build Docker images (multi-stage)

# Single test
cd backend && uv run pytest tests/test_<filename>.py -v

# TypeScript check
cd frontend && npx tsc --noEmit
```

## Architecture

### Frontend (React 19 + TypeScript + Vite 8)

```
src/
├── api/           # API 客户端（JWT 自动注入，按领域拆分）
├── features/      # 页面组件（按领域：auth, dashboard, knowledge, patents, workflow, admin...）
├── components/    # 可复用组件
│   ├── layout/    # AppLayout, Sidebar, ProtectedRoute
│   ├── common/    # ErrorBoundary, LoadingSkeleton, LazyPage
│   ├── rich-editor/ # TipTap 富文本编辑器
│   └── ...
├── store/         # Zustand 5 状态管理（每个领域一个 store）
├── types/         # TypeScript 类型定义
├── routes/        # React Router v7（惰性加载所有页面）
├── hooks/         # 自定义 React Hooks
└── lib/           # 第三方库扩展
```

**Key Patterns:**

- 页面组件在 `features/`，可复用子组件在 `components/<domain>/`
- 惰性加载：所有页面通过 `lazyPage()` 包装，路由自动 code-split
- ErrorBoundary 包裹顶层 RouterProvider
- 骨架屏：PageSkeleton, CardSkeleton, TableSkeleton, ListSkeleton
- State management via Zustand stores (one per feature domain)
- All API calls through `src/api/` with automatic JWT token injection
- Build optimization: vendor/ui/state code splitting, esbuild minification, no Console in prod

### Backend (FastAPI + PostgreSQL)

```
backend/app/
├── main.py          # FastAPI 入口 + 路由挂载 + startup/shutdown 事件
├── middleware.py     # SecurityHeaders, RequestID, GlobalExceptionHandler, RequestLogging
├── rate_limit.py    # 内存滑动窗口限流器
├── logging_config.py # JSON 结构化日志（ENV=production）
├── auth.py          # JWT 认证 + bcrypt（生产环境强制 INNOVOS_JWT_SECRET）
├── database.py      # PostgreSQL 连接池 + db_session() 上下文管理器 + QueryBuilder
├── seed.py          # idempotent 种子数据 seed_if_empty()
├── api/             # 路由层（20+ Router）
│   ├── auth.py, tasks.py, analysis.py, patents.py
│   ├── knowledge.py, knowledge_bases.py, kb_tools.py
│   ├── workflow.py, workflow_steps/*.py
│   ├── evaluation.py, feedback.py, solutions.py
│   ├── notifications.py, conversion.py, sidebare.py, models.py, monitoring.py
│   └── admin/       # admin/users.py, admin/keys.py, admin/monitor.py, admin/patent_db.py, admin/settings.py
├── models/          # Pydantic 请求/响应模型
├── tables/          # PG 表定义（pg_schema.py，含 FK 约束 + 索引）
├── algorithm/       # 算法层
│   ├── ai_client.py      # AI 通信客户端（30s 超时）
│   ├── key_manager.py    # Provider-based Key 轮询管理
│   ├── crypto.py         # AES-256 Fernet 加密（随机盐，600K PBKDF2）
│   ├── model_registry.py # 2600+ 模型注册表（懒加载）
│   ├── model_runtime.py  # 模型运行时
│   ├── embedder.py, reranker.py, retriever.py
│   ├── pipeline.py       # 知识库管道
│   ├── analyzers/        # 分析器
│   └── knowledge/        # 知识库处理（processors, pipeline）
├── services/        # 业务逻辑层
│   ├── knowledge_base_service.py
│   ├── knowledge_item_service.py
│   ├── knowledge_job_manager.py  # 异步作业系统
│   ├── knowledge_orchestration_service.py
│   ├── knowledge_workflow_service.py
│   ├── knowledge_lock_manager.py
│   └── notification_service.py
└── data/            # 静态数据
```

**Key Patterns:**

- Direct PostgreSQL via psycopg2 with connection pool (max 50 connections)
- `with db_session() as db:` — 必须使用此模式确保连接归还
- Provider-based API Key management with round-robin and rate limiting
- AI integration via OpenAI-compatible SDK
- 6-Agent pipeline with async job processing
- All SQL parameterized with `?` placeholders; dynamic column names whitelisted

### Multi-Agent Architecture (ZR-MoA)

```
User Input → 知识库RAG检索 → 需求洞察Agent → 问题建模Agent
            → 专利分析Agent → 方案生成Agent → 方案评估Agent → 成果转化Agent
```

**Core Algorithm:** ZR-IPM (智融创新问题映射) — 87.4% accuracy for problem identification

**Four-Dimension Evaluation Engine:**

- Innovation Assessment (patent similarity, tech evolution)
- Feasibility Assessment (constraint reasoning, rule validation)
- Completeness Assessment (reasoning chain verification, cross-validation)
- Achievement Transformation Assessment (patent applicability, industry scenario matching)

### Database Schema (PostgreSQL, 15+ tables)

- `users` — 用户账户（admin/user 角色）
- `tasks` — 创新任务
- `analyses` — 冲突分析结果
- `solutions` — 创新方案
- `workflows` — 工作流状态 + Agent 步骤
- `patents` — 专利数据
- `evaluations` — 四维评估
- `feedbacks` — 用户反馈
- `api_keys` — AES-256 加密 API 密钥 + providers
- `notifications` — 通知
- `knowledge_bases` — 知识库
- `knowledge_items` — 知识项（含状态机）
- `knowledge_vectors` — 向量嵌入（pgvector, 4096维，FK约束）
- `knowledge_docs` — 知识库文档
- `model_providers` — AI 模型供应商
- `models` — 模型注册 (composite PK provider_id, model_id)
- `problem_modelings` — 问题建模
- `audit_logs` — 审计日志

### Key Configuration

Backend: `.env` (see `.env.example`)

```env
INNOVOS_ENCRYPT_KEY=       # 必须：Fernet 加密密钥（生产环境必填）
INNOVOS_JWT_SECRET=        # 必须：JWT 签名密钥（生产环境必填）
DATABASE_URL=              # PostgreSQL 连接串
ENV=production             # production 启用 JSON 日志
INNOVOS_ADMIN_USER=admin   # 可选：管理员用户名
INNOVOS_ADMIN_PASSWORD=    # 可选：管理员密码（未设置则自动生成随机密码）
```

## Development Notes

- **Type Safety:** TypeScript strict mode (frontend), Python type hints enforced (backend)
- **DB Connection must be closed:** Always use `with db_session() as db:` or `try/finally` with `get_db()`
- **Commit Style:** `<type>(<scope>): <description>` (feat, fix, refactor, docs, test, chore)
- **Branch Strategy:** main → develop → feature/fix/refactor branches
- **CORS:** Allows `localhost:5173` and `localhost:5174` (Vite dev servers)
- **JWT Tokens:** 24-hour expiry, sent via `Authorization: Bearer <token>` header
- **Database Init:** Automatic on backend startup (`init_db()` + `seed_if_empty()` in startup event)
- **Dev Servers:** Backend on `:8000`, Frontend on `:5173`
- **Seed:** First-run only — creates admin user if none exists. Does NOT overwrite existing admin password.
- **Encryption:** API keys encrypted with AES-256 Fernet + random salt (600K PBKDF2 iterations)
- **Rate Limiting:** per-IP sliding window (auth 10/min, API 60/min, in-memory, single-worker)
- **Security Headers:** CSP, HSTS, XFO, X-XSS-Protection, Referrer-Policy, Permissions-Policy
- **Build:** Code splitting (vendor/ui/state chunks), esbuild minification
- **Error Boundary:** Global React error boundary with professional Chinese error UI and reload button
