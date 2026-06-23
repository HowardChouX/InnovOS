# InnovOS 生产环境配置

## 环境变量

### 必填配置（AI API Keys + JWT 密钥）

```bash
# AI API Keys（环境变量注入，不存数据库）
# 格式：AI_{PROVIDER_ID}_API_KEY
AI_SILICON_API_KEY=sk-xxxxxxxxxxxxxxxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyyyyyyyyyyyyyyy

# JWT 密钥（用于 Token 签名）
# 生成: python3 -c "import secrets; print(secrets.token_hex(32))"
INNOVOS_JWT_SECRET=your-jwt-secret-here
```

### AI 配置

```bash
# AI 供应商配置（按需设置）
# 格式：AI_{PROVIDER_ID}_API_KEY / API_HOST / API_MODEL
AI_SILICON_API_KEY=sk-xxxxxxxxxxxxxxxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyyyyyyyyyyyyyyy
AI_DEEPSEEK_API_HOST=https://api.deepseek.com
```

### 数据库配置

```bash
# 数据库配置
# PostgreSQL 连接（从组件变量自动构建）
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=innovos
POSTGRES_PASSWORD=your-db-password-here
POSTGRES_DB=innovos
# 或直接指定完整 URL:
# DATABASE_URL=postgresql://innovos:password@localhost:5432/innovos
```

### 服务器配置

```bash
# 后端
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=warning

# 前端
VITE_API_BASE_URL=https://api.yourdomain.com
```

### CORS 配置

```bash
# 允许的域名（逗号分隔）
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## 部署步骤

### 1. 生成 JWT 密钥

```bash
# 生成 JWT 密钥
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo "INNOVOS_JWT_SECRET=$JWT_SECRET"
```

### 2. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
INNOVOS_JWT_SECRET=$JWT_SECRET
AI_SILICON_API_KEY=sk-xxxxxxxx
AI_SILICON_API_HOST=https://api.siliconflow.cn
AI_DEEPSEEK_API_KEY=sk-yyyyyyyy
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=innovos
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=innovos
CORS_ORIGINS=https://yourdomain.com
EOF
```

### 3. 启动服务

```bash
# 加载环境变量
source .env

# 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 启动前端（构建后）
cd frontend
npm run build
npx serve -s dist -l 3000
```

## 安全检查清单

- [ ] AI API Keys 已配置到环境变量
- [ ] JWT 密钥已生成并安全存储
- [ ] 默认管理员密码已修改
- [ ] HTTPS 已配置
- [ ] CORS 已限制域名
- [ ] 数据库访问权限已限制
- [ ] 日志级别设置为 warning
- [ ] 调试模式已关闭
