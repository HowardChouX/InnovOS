# InnovOS 生产环境配置

## 环境变量

### 必填配置

```bash
# 加密密钥（AES-256 Fernet）
# 生成: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
INNOVOS_ENCRYPT_KEY=your-encryption-key-here

# JWT 密钥（用于 Token 签名）
# 生成: python3 -c "import secrets; print(secrets.token_hex(32))"
INNOVOS_JWT_SECRET=your-jwt-secret-here
```

### AI 配置

```bash
# DeepSeek API Key（兜底，Key 池为空时使用）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# OpenAI API Base URL（可选）
OPENAI_BASE_URL=https://api.deepseek.com
```

### 数据库配置

```bash
# 数据库路径（生产环境建议使用 PostgreSQL）
DATABASE_URL=sqlite:///data/InnovOS_ACCOUNTS.db
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

### 1. 生成密钥

```bash
# 生成加密密钥
ENCRYPT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 生成 JWT 密钥
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo "INNOVOS_ENCRYPT_KEY=$ENCRYPT_KEY"
echo "INNOVOS_JWT_SECRET=$JWT_SECRET"
```

### 2. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
INNOVOS_ENCRYPT_KEY=$ENCRYPT_KEY
INNOVOS_JWT_SECRET=$JWT_SECRET
DEEPSEEK_API_KEY=sk-xxxxxxxx
DATABASE_URL=sqlite:///data/InnovOS_ACCOUNTS.db
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

- [ ] 加密密钥已生成并安全存储
- [ ] JWT 密钥已生成并安全存储
- [ ] 默认管理员密码已修改
- [ ] HTTPS 已配置
- [ ] CORS 已限制域名
- [ ] 数据库访问权限已限制
- [ ] 日志级别设置为 warning
- [ ] 调试模式已关闭
