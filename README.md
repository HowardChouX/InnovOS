# InnovOS — 创新智能操作系统

AI 驱动的多 Agent 协同创新问题求解平台。帮助技术团队从问题出发，通过需求洞察 → 问题建模 → 专利检索 → 方案生成 → 方案评估的全流程 AI 分析，生成创新方案。

## 技术栈

| 层   | 技术                                                                  |
| ---- | --------------------------------------------------------------------- |
| 后端 | Python 3.13, FastAPI, PostgreSQL 17 (pgvector)                        |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS v4                           |
| AI   | OpenAI SDK, 多 Provider 轮询（DeepSeek / SiliconFlow / DashScope 等） |
| 存储 | PostgreSQL（业务数据 + 向量）, MinIO/S3（文件对象存储）               |
| 部署 | Docker Compose, Nginx                                                 |

## 快速开始（Docker）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 INNOVOS_JWT_SECRET、POSTGRES_PASSWORD 等必填项

# 2. 启动
docker compose up -d --build

# 3. 访问
http://localhost
```

首次启动自动初始化数据库、应用迁移、加载模型注册表。管理员账号需手动设置（见下方说明）。

### 环境变量

| 变量                  | 必填 | 说明                                                      |
| --------------------- | ---- | --------------------------------------------------------- |
| `INNOVOS_JWT_SECRET`  | ✅   | JWT 签名密钥（生产必须设置强随机值）                      |
| `INNOVOS_ENCRYPT_KEY` | ✅   | 主加密密钥:加密数据库中存储的供应商 API Key (AES-256-GCM) |
| `POSTGRES_PASSWORD`   | ✅   | 数据库密码                                                |
| `MINIO_ROOT_PASSWORD` | ✅   | MinIO 管理员密码                                          |

### 管理员账号

系统**不会**自动创建管理员。需先注册一个普通用户，然后手动提升为超级用户：

```sql
-- 连接数据库后执行（以手机号定位用户）
UPDATE users SET is_superuser = TRUE WHERE phone = '<手机号>';
```

之后该用户即可访问所有 `/admin/*` 管理页面，并可在「用户管理」中提升其他用户。

### AI 密钥配置

API Key **不再通过环境变量配置**。所有 Provider / Key 由管理员登录后,在
`/admin/model-services` 页面录入数据库,系统使用 **AES-256-GCM** 加密存储
(主密钥由 `INNOVOS_ENCRYPT_KEY` 派生)。支持多 Key 轮询、failover、cooldown。

首次启动步骤:

1. 配置 `INNOVOS_ENCRYPT_KEY`(见 `.env.example`)
2. 启动后端,按上方说明设置管理员账号并登录
3. 进入"模型服务"页面,新建 Provider(SiliconFlow / DeepSeek / OpenAI / 阿里百炼等)
4. 为 Provider 添加 API Key(掩码显示,保存后永不回显明文)
5. 在系统设置中分配 chat / embedding / rerank / ocr / extract 默认模型

## 开发模式

```bash
make install     # 安装依赖（uv sync + npm install）
make dev         # 启动开发环境（后端 :8000 + 前端 :5173）
make test        # 运行全部测试
make lint        # 代码检查
make format      # 自动格式化
make quality     # 完整质量门禁
```

### PostgreSQL socket path

`make dev` starts the local PostgreSQL cluster via `sudo pg_ctl`. The default
Unix socket directory is redirected to `/tmp` (via `pg_ctl -o "-k /tmp"`)
because `/run/postgresql` is not present on this machine. The backend
connects through `DATABASE_URL=...@localhost:5432/innovos?host=/tmp` so
psycopg2 uses the same socket.

To use a different socket directory, override `PG_SOCKET_DIR`:

```bash
make dev PG_SOCKET_DIR=/home/you/.pgsock
```

You will need to create the directory yourself first.

> 提示：`@localhost:5432` 是 URL 占位，实际连接路径由 `?host=/tmp` 决定（Unix socket）。

## 项目结构

```
InnovOS/
├── backend/               # Python FastAPI 后端
│   ├── app/               # 应用代码
│   │   ├── api/           # HTTP 路由
│   │   ├── algorithm/     # AI 核心（模型/分析器/RAG）
│   │   ├── services/      # 业务逻辑
│   │   ├── tables/        # 数据库 DDL
│   │   └── main.py        # 应用入口
│   ├── tests/             # 测试
│   └── Dockerfile
├── frontend/              # React 前端
│   ├── src/
│   │   ├── features/      # 功能页面
│   │   ├── components/    # 可复用组件
│   │   ├── store/         # Zustand 状态管理
│   │   ├── api/           # API 客户端
│   │   └── routes/        # 路由定义
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── .env
```

## 核心功能

- **AI 分析管线**: 需求洞察（7 分析器并行）→ 问题建模 → 专利检索 → 方案生成 → 四维评估
- **知识库**: 文档上传 → 解析 → 分块 → 嵌入 → 向量检索（RAG）
- **异步作业系统**: 5 种作业类型，数据库持久化队列，失败重试 3 次 + 指数退避
- **模型注册表**: 2600+ 模型自动检测，17 个供应商，多 Key 轮询
- **自动备份**: 每日 03:00 数据库快照，保留 30 天

## 安全特性

- JWT 24h 过期，`__Host-token` httpOnly Secure Cookie + Bearer 头双通道
- Token 版本号控制，管理员可一键撤销所有用户 Token
- API Key 仅从环境变量读取，不存数据库
- 操作审计日志（增删改操作写入 `audit_log` 表）
- 请求限流（登录 10/min, 注册 3/5min, API 120/min）
- 安全响应头（CSP、HSTS、X-Frame-Options）
- 文件上传大小限制（50MB/文件, 500MB/批次）
- 错误信息生产环境脱敏

## 文档

| 文档                             | 说明                            |
| -------------------------------- | ------------------------------- |
| [系统架构](docs/architecture.md) | 整体架构、模块划分、AI 调用链路 |
| [开发指南](docs/development.md)  | 环境搭建、命令、规范、项目结构  |
| [部署指南](docs/deployment.md)   | Docker 部署、环境变量、生产配置 |
| [AGENTS.md](AGENTS.md)           | AI 辅助开发约束与规范           |

## 许可证

[MIT](LICENSE)
