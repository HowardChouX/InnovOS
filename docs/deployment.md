# 部署指南

## Docker 部署（推荐）

### 前置条件

- Docker Engine 24+
- Docker Compose v2

### 部署步骤

```bash
# 1. 克隆项目
git clone <repo> && cd InnovOS

# 2. 配置环境变量
#    复制 .env.example 或创建 .env，至少需设置：
#     - INNOVOS_JWT_SECRET    — JWT 签名密钥
#     - POSTGRES_PASSWORD     — 数据库密码
#     - MINIO_ROOT_PASSWORD   — MinIO 管理员密码
#     - AI_SILICON_API_KEY    — AI 供应商密钥（按需）

# 3. 启动
docker compose up -d --build
```

### 架构

```
docker-compose.yml 定义 5 个服务：

postgres      — PostgreSQL 17 + pgvector
minio         — S3 兼容对象存储（文件持久化）
minio-setup   — 初始化 MinIO bucket（一次性）
backend       — FastAPI 应用
frontend      — Nginx 静态托管 + API 反向代理（端口 80）
```

### 环境变量

#### 必填

| 变量                  | 说明                                 |
| --------------------- | ------------------------------------ |
| `INNOVOS_JWT_SECRET`  | JWT 签名密钥（生产必须设置强随机值） |
| `POSTGRES_PASSWORD`   | 数据库密码                           |
| `MINIO_ROOT_PASSWORD` | MinIO 管理员密码                     |

#### AI 供应商

API Key 全部通过环境变量注入，不存储在数据库中：

```
AI_{PROVIDER_ID}_API_KEY     — 单 Key
AI_{PROVIDER_ID}_API_KEY_1   — 多 Key 轮询（添加 _1, _2 后缀）
AI_{PROVIDER_ID}_API_HOST    — API 端点地址（可选，有默认值）
```

示例：

```env
AI_SILICON_API_KEY=sk-xxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyy
AI_DEEPSEEK_API_HOST=https://api.deepseek.com
```

#### 可选

| 变量         | 默认值             | 说明                                          |
| ------------ | ------------------ | --------------------------------------------- |
| `S3_BUCKET`  | `innovos-files`    | MinIO 存储桶名称                              |
| `S3_REGION`  | `us-east-1`        | S3 区域                                       |
| `PUBLIC_URL` | `http://localhost` | 公网访问地址                                  |
| `REDIS_URL`  | —                  | Redis 连接（未配置则使用 fakeredis 内存模拟） |

### 数据持久化

Docker Compose 使用 3 个命名卷持久化数据：

| 卷                | 挂载点                     | 说明           |
| ----------------- | -------------------------- | -------------- |
| `postgres_data`   | `/var/lib/postgresql/data` | 数据库文件     |
| `minio_data`      | `/data`                    | MinIO 对象存储 |
| `backend_uploads` | `/app/data/uploads`        | 上传文件缓存   |

### HTTPS（可选）

若需 HTTPS，需配置域名 + 证书：

1. 取消 `frontend/nginx.conf` 中 SSL 相关注释
2. 配置证书路径
3. 更新 `PUBLIC_URL` 为 `https://yourdomain.com`

## 安全清单

- [ ] `INNOVOS_JWT_SECRET` 已设置为安全随机值
- [ ] `POSTGRES_PASSWORD` 已设置为强密码
- [ ] `MINIO_ROOT_PASSWORD` 已设置
- [ ] HTTPS 已配置（生产环境必须）
- [ ] AI API Key 已配置到环境变量
- [ ] CORS 已限制域名
- [ ] 数据库端口未公开到公网
- [ ] 文件上传大小限制已生效（50MB/文件, 500MB/批次）

## 维护

### 数据库备份

默认每日 03:00 自动执行 `pg_dump` 快照，保留最近 30 天：

```bash
# 手动触发备份
make db-backup
```

备份文件存储在 `backend/backups/` 目录。

### 日志

- Docker logging driver: `json-file`
- 日志轮转: 最大 10MB/文件，保留 3 个文件
- 后端日志可通过 `docker compose logs backend` 查看
- 生产环境日志级别可通过 `ENV=production` 设置为结构化 JSON 格式
