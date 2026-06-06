# API Key 认证失败修复方案

## 问题描述
系统提示 401 认证错误，API key 失效：
```
Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key: ****UAZC is invalid'}}
```

## 根本原因
1. 数据库中只有一个 DeepSeek API key，但它已失效
2. 没有备用 API key
3. 环境变量中没有配置 `DEEPSEEK_API_KEY` 作为 fallback

## 快速修复（2步）

### 步骤1：配置有效的 DeepSeek API Key

编辑 `/home/chou/InnovOS/backend/.env` 文件，填入有效的 API key：

```bash
# 找到这个字段
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here

# 替换为你实际的 API key
DEEPSEEK_API_KEY=sk-xxxxxxxxx...
```

获取 DeepSeek API Key：
- 访问 https://platform.deepseek.com/
- 注册/登录后创建 API key

### 步骤2：重启后端服务

```bash
cd /home/chou/InnovOS/backend
uvicorn app.main:app --reload
```

## 可选：添加新的 API Key（通过管理界面）

1. 登录管理界面
2. 进入 **Keys** 页面
3. 点击 **添加 Key**
4. 输入：
   - Key 名称：新 key 的名称
   - API Key：有效的 API key（sk-...）
   - API Base URL：https://api.deepseek.com
   - 模型：deepseek-chat
5. 点击 **测试** 验证 key 是否有效
6. 保存

## 验证修复

重启服务后，测试 AI 功能是否正常工作：
```bash
cd /home/chou/InnovOS/backend
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"problem": "测试"}'
```

## 代码修改说明

已自动修改以下文件以支持环境变量 fallback：

1. **`backend/.env.example`** - 添加注释说明 API key 的用途
2. **`backend/.env`** - 创建配置文件，需要用户填入 API key
3. **`backend/app/algorithm/key_manager.py`** - 修改 `_get_next_key()` 方法，在 API key 池为空时自动使用环境变量中的 `DEEPSEEK_API_KEY`

**修改前：** 没有可用 API key 时直接报错
**修改后：** 没有可用 API key 时，检查是否有环境变量中的 `DEEPSEEK_API_KEY`，如有则使用它

## 相关文件
- 配置：`/home/chou/InnovOS/backend/.env`
- 示例：`/home/chou/InnovOS/backend/.env.example`
- API Key 管理器：`/home/chou/InnovOS/backend/app/algorithm/key_manager.py`
- AI 客户端：`/home/chou/InnovOS/backend/app/algorithm/ai_client.py`
