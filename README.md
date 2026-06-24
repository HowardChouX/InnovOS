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

首次启动自动初始化数据库、创建管理员账号、加载模型注册表。

### 环境变量

| 变量                  | 必填 | 说明                                        |
| --------------------- | ---- | ------------------------------------------- |
| `INNOVOS_JWT_SECRET`  | ✅   | JWT 签名密钥（生产必须设置强随机值）        |
| `POSTGRES_PASSWORD`   | ✅   | 数据库密码                                  |
| `MINIO_ROOT_PASSWORD` | ✅   | MinIO 管理员密码                            |
| `AI_*_API_KEY`        | 按需 | AI 供应商密钥，格式 `AI_{供应商ID}_API_KEY` |

### AI 密钥配置

API Key 通过环境变量注入，不存储在数据库中。支持多 Key 轮询：

```env
AI_SILICON_API_KEY=sk-xxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyy
AI_DEEPSEEK_API_HOST=https://api.deepseek.com
AI_SILICON_API_KEY_1=sk-zzz    # 多 Key 添加 _1, _2 后缀
```

## 开发模式

```bash
make install     # 安装依赖（uv sync + npm install）
make dev         # 启动开发环境（后端 :8000 + 前端 :5173）
make test        # 运行全部测试
make lint        # 代码检查
make format      # 自动格式化
make quality     # 完整质量门禁
```

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
