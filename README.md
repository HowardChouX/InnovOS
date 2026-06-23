# InnovOS — 创新智能操作系统

AI 驱动的创新分析平台，帮助技术团队从问题出发，通过多 Agent 协作生成创新方案。

## 技术栈

| 层      | 技术                                                            |
| ------- | --------------------------------------------------------------- |
| 后端    | Python 3.11+, FastAPI, PostgreSQL (pgvector)                    |
| 前端    | React 19, TypeScript, Vite 8, Tailwind CSS v4                   |
| AI 引擎 | OpenAI SDK, 2600+ 模型注册表, 多 Provider 轮询                  |
| 存储    | PostgreSQL (主数据), 本地文件系统 (文件存储, MinIO/S3 预留配置) |
| 部署    | Docker Compose, Nginx (反向代理 + HTTPS)                        |

## 快速开始（Docker）

```bash
# 1. 克隆
git clone <repo> && cd InnovOS

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入以下必填项：
#   INNOVOS_JWT_SECRET=    # JWT 签名密钥
#   INNOVOS_ADMIN_PASSWORD= # 管理员密码
#   AI_SILICON_API_KEY=     # AI 供应商密钥（按需）

# 3. 启动
docker compose up -d --build

# 4. 访问
http://localhost
```

首次启动会自动初始化数据库、创建管理员账号、加载模型注册表。

### 环境变量说明

| 变量                     | 必填 | 说明                                           |
| ------------------------ | ---- | ---------------------------------------------- |
| `INNOVOS_JWT_SECRET`     | ✅   | JWT 签名密钥（生产必须设置）                   |
| `INNOVOS_ADMIN_PASSWORD` | ✅   | 管理员密码（不填则自动生成随机密码打印到日志） |
| `POSTGRES_PASSWORD`      | ✅   | 数据库密码                                     |
| `MINIO_ROOT_PASSWORD`    | ✅   | MinIO 管理员密码                               |
| `AI_*_API_KEY`           | 按需 | AI 供应商密钥，格式 `AI_{供应商ID}_API_KEY`    |

### AI 密钥配置

API Key 全部通过环境变量注入，不存储在数据库中：

```env
AI_SILICON_API_KEY=sk-xxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyy
AI_DEEPSEEK_API_HOST=https://api.deepseek.com
```

多 Key 轮询：`AI_SILICON_API_KEY_1`、`AI_SILICON_API_KEY_2`...

## 开发模式

```bash
make install     # 安装依赖
make dev         # 启动 PostgreSQL + 后端(:8000) + 前端(:5173)
make test        # 运行全部测试
make lint        # 代码检查
make format      # 自动格式化
```

## 项目结构

```
    backend/
  app/
    api/            # FastAPI 路由
    algorithm/      # AI 核心（模型/嵌入/重排/检索/管线）
    services/       # 业务逻辑（知识库/作业系统/通知）
    tables/         # 数据库 schema
    main.py         # 应用入口
  tests/            # 后端测试
frontend/
  src/
    features/       # 功能页面
    components/     # 公共组件
    store/          # Zustand 状态管理
    api/            # API 客户端
    routes/         # 路由定义
  Dockerfile        # nginx 多阶段构建
```

## 架构

```
用户 → Nginx (80/443)
         ├── 静态文件 (SPA)
         └── /api/* → FastAPI
                        ├── PostgreSQL (业务数据 + 向量)
                        └── MinIO/S3 (文件存储)
```

- **AI 分析管线**: 需求洞察 → 问题建模 → 专利检索 → 方案生成 → 评估 → 转化（全流程后端集成）
- **知识库**: 上传文档 → 分块 → 嵌入 → 向量检索引擎
- **作业系统**: 异步任务队列，失败重试 3 次 + 指数退避
- **模型注册表**: 2600+ 模型自动检测，支持 17 个供应商

## 部署

### 生产环境（云服务器）

```bash
# 1. 安装 Docker + Docker Compose
curl -fsSL https://get.docker.com | sh

# 2. 配置
git clone <repo> && cd InnovOS
cp .env.example .env
# 编辑 .env，必须设置：
#   INNOVOS_JWT_SECRET
#   POSTGRES_PASSWORD
#   MINIO_ROOT_PASSWORD
#   AI_*_API_KEY（根据使用的 AI 供应商）

# 3. 启动
docker compose up -d --build

# 4. HTTPS（可选 - 需域名 + 证书）
# 取消 frontend/nginx.conf 中 SSL 块的注释
# 配置 Let's Encrypt 证书
```

### 关键安全配置

- JWT Token 通过 `__Host-token` httpOnly Secure Cookie 传输（防 XSS），同时支持 `Authorization: Bearer` 请求头
- JWT Token Version：每个 Token 携带 `token_version`，每次请求与数据库比对，管理员可一键撤销所有用户 Token
- API Key 仅从环境变量读取（不存数据库）
- 操作审计日志（增删改操作写入 `audit_log` 表）
- 文件上传大小限制（50MB/文件，500MB/批次）
- 请求速率限制（登录 10次/分，注册 3次/分）
- 安全响应头（CSP、HSTS、X-Frame-Options 等）
- 错误信息生产环境脱敏

## 测试

```bash
# 后端测试
cd backend && uv run pytest tests/ -v

# 前端测试
cd frontend && npm test

# 全量
make test
```

## 文档

- `docs/DEVELOPMENT_GUIDE.md` — 开发文档 v4.0
- `AGENTS.md` — AI 辅助开发约束与规范
- 应用内 `/guide` — 面向普通用户的使用指南

## 许可证

私有项目 — 济南一竖光年人工智能科技有限公司
