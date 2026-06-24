# 系统架构

## 技术栈

| 层   | 技术                                                         |
| ---- | ------------------------------------------------------------ |
| 后端 | Python 3.13, FastAPI, PostgreSQL 17 (pgvector), Redis        |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand 5       |
| AI   | OpenAI SDK v2, 多 Provider 轮询（DeepSeek / SiliconFlow 等） |
| 存储 | PostgreSQL（业务数据 + 向量）, MinIO/S3（文件对象存储）      |
| 部署 | Docker Compose, Nginx（静态托管 + 反向代理）                 |

## 架构图

```
用户 → Nginx (80)
         ├── 静态文件 (SPA)
         └── /api/* → FastAPI
                        ├── PostgreSQL (业务数据 + pgvector)
                        ├── MinIO/S3 (文件存储)
                        └── AI Provider API (外部)
```

## 后端模块

```
backend/app/
├── main.py              # FastAPI 入口 — 启动/关闭钩子、路由注册
├── auth.py              # JWT 认证（bcrypt + 24h Token）
├── database.py          # PostgreSQL 连接池（psycopg2, max 50）
├── middleware.py         # 安全头、请求 ID、全局异常处理
├── logging_config.py    # 结构化 JSON 日志
├── rate_limit_redis.py  # Redis 滑动窗口限流
├── audit.py             # 审计日志
│
├── api/                 # HTTP 路由（按领域分组）
│   ├── auth.py / tasks.py / analysis.py
│   ├── knowledge.py / knowledge_bases.py / kb_tools.py
│   ├── solutions.py / evaluation.py / feedback.py
│   ├── patents.py / conversion.py / modeling.py
│   ├── workflow.py / workflow_steps/
│   ├── notifications.py / sidebar.py / users.py
│   └── admin/           # 管理员子路由（6 个模块）
│
├── algorithm/           # AI 核心
│   ├── ai_client.py     # AI 客户端（Key 池轮询、并发控制、重试）
│   ├── key_manager.py   # API Key 管理（环境变量注入）
│   ├── model_registry.py    # 2600+ 模型注册表
│   ├── model_runtime.py     # 运行时模型配置
│   ├── model_service.py     # 统一模型服务
│   ├── providers_registry.py # 供应商注册表
│   ├── base.py / zr_ipm.py  # 分析器基类 + ZR-IPM 引擎
│   ├── analyzers/            # TRIZ 分析器套件
│   │   ├── demand_portrait.py / problem_modeling.py
│   │   ├── evolution_analyzer.py / sufield_analyzer.py
│   │   ├── ifr_generator.py / resource_analyzer.py
│   │   └── thinking_tools/   # 金鱼法、九屏幕、STC
│   ├── knowledge/            # RAG 引擎
│   │   ├── chunker.py / embedder.py / reranker.py
│   │   ├── retriever.py / pipeline.py / vector_store.py
│   │   ├── html_to_markdown.py / url_fetcher.py
│   │   └── processors/       # 文件处理器
│   ├── patent_extractor.py / patent_search_engine.py
│   └── evaluation_service.py
│
├── services/            # 业务逻辑层
│   ├── knowledge_base_service.py / knowledge_item_service.py
│   ├── knowledge_job_manager.py / knowledge_jobs/
│   ├── knowledge_orchestration_service.py
│   ├── knowledge_workflow_service.py
│   ├── knowledge_lock_manager.py
│   ├── file_storage_service.py
│   └── backup_service.py     # 每日自动数据库快照
│
├── models/              # Pydantic 请求/响应模型
├── tables/              # PostgreSQL DDL 定义
│   ├── pg_schema.py     # 全部表的 CREATE 语句
│   └── models.py        # models 表独立 DDL
├── core/                # 配置 + 安全
│   ├── config.py        # Pydantic Settings
│   └── security.py      # bcrypt + JWT
└── crd/                 # 数据访问层
    └── users.py         # 用户 CRUD
```

## 前端模块

```
frontend/src/
├── main.tsx / App.tsx / index.css
├── features/            # 页面（按功能域组织）
│   ├── auth/            # 登录/注册
│   ├── dashboard/       # 首页（任务输入、分析结果、方案）
│   ├── knowledge/       # 知识库
│   ├── patents/         # 专利检索
│   ├── patent_conversion/ # 专利转化
│   ├── history_solutions/ # 历史方案
│   ├── admin/           # 管理员页面
│   ├── monitor/         # 监控面板
│   └── guide/           # 使用指南
├── components/          # 可复用组件
│   ├── layout/          # AppLayout, Sidebar, ProtectedRoute
│   ├── common/          # ErrorBoundary, LoadingSkeleton, LazyPage
│   ├── ui/              # 通用 UI 组件
│   └── diagram/         # 图表组件
├── api/                 # API 客户端（JWT 自动注入）
├── store/               # Zustand 状态管理（12 stores）
├── types/               # TypeScript 类型定义
├── routes/              # React Router v7 路由（懒加载）
├── hooks/ / lib/ / utils/
```

## AI 调用链路

```
前端请求 → API 路由 → ModelService（3 层 fallback）
  → ProviderRegistry → KeyManager（环境变量 Key 池轮询）
    → ModelRuntime（API 路径补全 /v1）
      → AIClient（OpenAI SDK v2, 重试 3 次）
        → 目标 AI 模型
```

## 知识库管线

```
上传文档 → KnowledgePipeline
   → 解析（PDF/DOCX/TXT/MD）
     → 分块（chunker）
       → 嵌入（embedder）
         → 写入 pgvector（vector_store）
           → 检索（retriever + reranker）
```

## 作业系统

5 种作业类型，异步队列 + 数据库持久化 + 重试 3 次 + 指数退避：

| 作业类型                       | 说明                        |
| ------------------------------ | --------------------------- |
| `prepare-root`                 | 处理目录容器，递归入队子项  |
| `index-documents`              | 索引叶子项（文件/笔记/URL） |
| `check-file-processing-result` | 轮询外部文件处理结果        |
| `delete-subtree`               | 递归删除子项 + 向量         |
| `reindex-subtree`              | 重置并重新索引子树          |

## 数据库

PostgreSQL 16 + pgvector，约 22 张表：

- **用户体系**: users, audit_log
- **核心业务**: tasks, analyses, solutions, workflows, workflow_steps
- **评估反馈**: evaluations, feedbacks, problem_modelings
- **知识库**: knowledge_bases, knowledge_items, knowledge_groups, knowledge_docs, knowledge_vectors, knowledge_jobs
- **专利**: patents, patent_vectors
- **系统**: notifications, system_settings, models, model_providers

## 安全

- JWT 24h 过期，`__Host-token` httpOnly Secure Cookie + Bearer 头双通道
- Token 版本号（`users.token_version`），管理员可一键撤销
- API Key 仅从环境变量读取，不存数据库
- 操作审计日志（`audit_log` 表）
- 请求限流（登录 10/min, 注册 3/5min, API 120/min）
- 安全响应头（CSP, HSTS, XFO）
- 文件上传大小限制
