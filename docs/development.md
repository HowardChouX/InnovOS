# 开发指南

## 环境要求

- Python 3.13
- Node.js 20+
- PostgreSQL 17 (pgvector)
- Redis（可选，限流降级使用 fakeredis）

## 快速开始

```bash
# 1. 安装依赖
make install

# 2. 确保 PostgreSQL 已启动（含 pgvector 扩展）
#    配置 backend/.env 中的 DATABASE_URL

# 3. 启动开发服务
make dev      # 后端 :8000 + 前端 :5173
```

首次启动会自动初始化数据库表、创建管理员账号、加载模型注册表。

## 开发命令

| 命令                | 说明                                                       |
| ------------------- | ---------------------------------------------------------- |
| `make install`      | 安装全部依赖（uv sync + npm install）                      |
| `make dev`          | 启动开发环境                                               |
| `make stop`         | 停止开发环境                                               |
| `make test`         | 运行全部测试                                               |
| `make lint`         | 代码检查（ESLint + Ruff + Prettier）                       |
| `make format`       | 自动格式化                                                 |
| `make typecheck`    | 类型检查（tsc + mypy）                                     |
| `make build`        | 前端生产构建                                               |
| `make security`     | 安全扫描（Bandit + npm audit）                             |
| `make quality`      | 完整质量门禁（lint → typecheck → test → build → security） |
| `make db-backup`    | 手动数据库快照备份                                         |
| `make docker-build` | 构建 Docker 镜像                                           |
| `make docker-up`    | 启动 Docker 环境                                           |
| `make docker-down`  | 停止 Docker 环境                                           |

## 项目结构

```
InnovOS/
├── backend/              # Python FastAPI 后端
│   ├── app/              # 应用代码
│   ├── tests/            # 测试
│   ├── backups/          # 数据库快照备份
│   ├── pyproject.toml    # Python 项目配置
│   └── Dockerfile        # 多阶段构建
├── frontend/             # React 前端
│   ├── src/              # 源码
│   ├── Dockerfile        # nginx 多阶段构建
│   └── nginx.conf        # 生产 Nginx 配置
├── docker-compose.yml    # Docker 编排
└── .env                  # 环境变量（不提交 Git）
```

## 开发规范

### 后端

- PEP 8 风格，行宽 120 字符
- 函数参数和返回值使用类型注解
- 数据库操作使用 `with db_session() as db:` 上下文管理器
- 参数化 SQL 查询（禁止 f-string 拼接 SQL）
- API 路由在 `api/` 中，复杂业务逻辑在 `services/` 中
- TRIZ 分析器继承 `AIAnalyzer` 基类

### 前端

- 函数组件 + Hooks，单文件不超过 200 行
- 页面放 `features/<domain>/`，子组件放 `components/<domain>/`
- 使用 TypeScript strict 模式，禁止 `any`
- 样式使用 Tailwind CSS v4 工具类
- 图标：导航用 FontAwesome 6，其他用 Lucide React
- API 调用走 `api/client.ts`（JWT 自动注入）
- 状态管理用 Zustand，模板：loading / error / data 三态

### Git

```
<type>(<scope>): <描述>

类型: feat / fix / refactor / style / docs / test / chore
```

### 数据库

- PostgreSQL only（SQLite 已移除）
- pgvector 扩展用于向量相似度搜索
- 所有表定义在 `tables/pg_schema.py` 中
- 时间戳使用 `TEXT` 格式 `YYYY-MM-DD HH24:MI:SS`（向后兼容），新列推荐 `TIMESTAMPTZ`
- 建表和迁移通过 `init_all_tables()` 幂等执行

### 邮箱验证（OTP）

- **开发环境 SMTP**: `docker compose --profile mail up mailpit` 启动 Mailpit（localhost:1025）
- **临时关闭 SMTP**: 设 `EMAIL_OTP_SOFT_FAIL=true`，验证码打印到后端日志 `[DEV OTP] code=...`
- **环境变量**: 见 `.env.example` 中 `# ── Email OTP 验证 ──` 章节
- **前端**: `/verify-email?email=...` 页面接收 6 位 OTP，满位自动 submit
- **测试**: `tests/test_email_verification.py` 使用 SQLite 内存替代 PostgreSQL（服务层 + 路由层合同测试）

### 测试

```bash
# 后端
cd backend && uv run pytest tests/ -v --cov=app

# 前端
cd frontend && npm test

# 全部
make test
```

后端覆盖率阈值 60%（全局），新增代码建议 80%+。
