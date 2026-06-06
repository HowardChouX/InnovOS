# InnovOS API 设计规范

## 1. 接口规范

### 1.1 基础 URL

| 环境 | URL |
|------|-----|
| 开发 | http://localhost:8000 |

### 1.2 通用响应格式

```json
// 成功响应
{
    "code": 200,
    "message": "success",
    "data": {}
}

// 错误响应
{
    "detail": "人类可读的错误信息"
}
```

### 1.3 HTTP 状态码使用规范

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | 成功 | 所有正常响应 |
| 400 | 请求错误 | 参数校验失败 |
| 401 | 未认证 | 未提供或 token 过期 |
| 404 | 资源不存在 | 查询的资源不存在 |
| 500 | 服务器错误 | 未预期的服务异常 |

## 2. API 端点定义

### 2.1 认证模块

#### POST /api/auth/register
注册新用户

**请求体：**
```json
{
    "username": "string (至少2字符)",
    "password": "string (至少4字符)"
}
```

**响应 (200)：**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
        "id": 1,
        "username": "example_user",
        "created_at": "2026-06-05T12:00:00Z"
    }
}
```

#### POST /api/auth/login
用户登录

**请求体：**
```json
{
    "username": "string",
    "password": "string"
}
```

**响应 (200)：**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
        "id": 1,
        "username": "example_user",
        "created_at": "2026-06-05T12:00:00Z"
    }
}
```

#### GET /api/auth/me
获取当前用户信息（需认证）

**响应 (200)：**
```json
{
    "id": 1,
    "username": "example_user",
    "created_at": "2026-06-05T12:00:00Z"
}
```

### 2.2 任务管理模块

#### GET /api/tasks
获取任务列表（需认证）

**响应 (200)：**
```json
{
    "code": 200,
    "data": [
        {
            "id": "1",
            "title": "新能源汽车电池热管理技术改进",
            "description": "如何在保证电池能量密度的同时...",
            "tags": ["电池安全", "能量密度"],
            "status": "completed",
            "createdAt": "2026-06-05T12:00:00Z",
            "updatedAt": "2026-06-05T12:00:00Z"
        }
    ],
    "message": "success"
}
```

#### POST /api/tasks
创建新任务（需认证）

**请求体：**
```json
{
    "title": "string (必填)",
    "description": "string (必填)",
    "tags": ["string"] (可选)
}
```

#### GET /api/tasks/{task_id}
获取任务详情（需认证）

#### DELETE /api/tasks/{task_id}
删除任务（需认证）

### 2.3 分析模块

#### GET /api/analysis/{task_id}
获取任务冲突分析结果（需认证，不存在则自动创建默认数据）

**响应 (200)：**
```json
{
    "code": 200,
    "data": {
        "id": "1",
        "taskId": "1",
        "centerNode": { "id": "center", "label": "核心冲突", "description": "...", "type": "center" },
        "satelliteNodes": [
            { "id": "s1", "label": "能量密度", "sublabel": "(提升)", "type": "satellite", "color": "#06b6d4", "position": "top" }
        ],
        "edges": [ { "sourceId": "center", "targetId": "s1", "label": "冲突" } ],
        "principles": ["分割原理", "动态化原理"]
    },
    "message": "success"
}
```

### 2.4 方案模块

#### GET /api/solutions/{task_id}
获取任务创新方案列表（需认证，不存在则自动创建默认数据）

**响应 (200)：**
```json
{
    "code": 200,
    "data": [
        {
            "id": "1", "taskId": "1",
            "title": "固态电池 + 界面改性技术",
            "description": "通过固态电解质替换液态电解质...",
            "principles": ["复合材料原理", "参数变化原理"],
            "confidenceScore": 92,
            "patentReferences": ["p1", "p3"],
            "rating": 5
        }
    ],
    "message": "success"
}
```

### 2.5 专利模块

#### GET /api/patents/search
专利搜索（公开接口）

**查询参数：**
```
q    string  搜索关键词（可选，为空返回前5条）
```

**响应 (200)：**
```json
{
    "code": 200,
    "data": [
        {
            "id": "1", "title": "一种高安全性固态电池及其制备方法",
            "abstract": "本发明提供了一种高安全性固态电池...",
            "applicants": ["宁德时代新能源科技股份有限公司"],
            "inventors": ["张明", "李华"],
            "filingDate": "2023-05-16",
            "publicationDate": "2024-01-20",
            "patentNumber": "CN202310456789.1",
            "ipcCodes": ["H01M10/056", "H01M10/0525"],
            "relevanceScore": 98
        }
    ],
    "total": 1,
    "message": "success",
    "code": 200
}
```

#### GET /api/patents/stats
专利统计数据（公开接口）

### 2.6 工作流模块

#### GET /api/workflow/{task_id}
获取任务工作流状态（需认证，不存在则自动创建默认数据）

**响应 (200)：**
```json
{
    "code": 200,
    "data": {
        "id": "1", "taskId": "1",
        "status": "running",
        "steps": [
            { "agentId": "agent1", "agentType": "problem_analysis", "agentLabel": "需求洞察Agent", "status": "completed", "description": "...", "duration": "2.1s" }
        ],
        "createdAt": "2026-06-05T12:00:00Z"
    },
    "message": "success"
}
```

### 2.7 评估模块

#### POST /api/evaluation/{solution_id}
创建或获取方案评估结果（需认证，自动返回 mock 评分）

**响应 (200)：**
```json
{
    "code": 200,
    "data": {
        "id": "1",
        "solutionId": "1",
        "dimension": "comprehensive",
        "score": 83.5,
        "details": {
            "scores": { "innovation": 85.0, "feasibility": 78.0, "completeness": 88.0, "conversion": 72.0 },
            "overall": 83.5,
            "grade": "B+",
            "strengths": ["创新性突出", "推理过程完整"],
            "weaknesses": ["转化路径不够清晰"],
            "recommendations": ["补充成本分析", "明确产业化路径"]
        },
        "status": "completed",
        "createdAt": "2026-06-05T12:00:00Z"
    },
    "message": "success"
}
```

#### GET /api/evaluation/{solution_id}/history
获取方案评估历史（需认证）

### 2.8 反馈模块

#### POST /api/feedback
提交用户反馈（需认证）

**请求体：**
```json
{
    "solution_id": "int",
    "rating": "int (1-5)",
    "feedback_type": "string (可选)",
    "comments": "string (可选)"
}
```

#### GET /api/feedback/{solution_id}
获取方案的所有反馈（需认证）

### 2.9 API Key 管理模块（仅管理员）

#### GET /api/keys
获取 API Key 列表

#### POST /api/keys
创建 API Key

**请求体：**
```json
{
    "keyName": "DeepSeek-1",
    "apiKey": "sk-xxxxxxxxxxxxxxxx",
    "apiBaseUrl": "https://api.deepseek.com",
    "apiModel": "deepseek-v4-flash,deepseek-v4-pro",
    "priority": 0,
    "maxRpm": 60
}
```

#### PUT /api/keys/{key_id}
更新 API Key（支持部分更新）

#### DELETE /api/keys/{key_id}
删除 API Key

#### POST /api/keys/{key_id}/test
测试 API Key 连接

### 2.10 分析触发模块

#### POST /api/analysis/{task_id}/trigger
触发 AI 分析（需认证）

**响应 (200)：**
```json
{
    "code": 200,
    "data": {
        "id": "10",
        "taskId": "10",
        "centerNode": { "id": "center", "label": "核心冲突", "description": "...", "type": "center" },
        "satelliteNodes": [
            { "id": "s1", "label": "能量密度", "sublabel": "(提升)", "type": "satellite", "color": "#60a5fa", "position": "top" }
        ],
        "edges": [ { "sourceId": "center", "targetId": "s1", "label": "冲突" } ],
        "principles": ["分割原理", "动态化原理", "复合材料原理"]
    },
    "message": "分析完成"
}
```

### 2.11 健康检查

#### GET /api/health
服务健康检查（公开接口）

**响应：**
```json
{
    "status": "ok",
    "message": "InnovOS API is running"
}
```

## 3. 认证与鉴权

### 3.1 JWT Token 规范

Token 存储 `user_id` 和 `exp`，24h 过期。

```
Authorization: Bearer <token>
```

### 3.2 用户认证流程

```
注册 → 返回 access_token + user
登录 → 返回 access_token + user
请求头携带 Authorization: Bearer <token>
失败返回 401
```

## 4. 错误码定义

| HTTP 状态码 | 说明 |
|------------|------|
| 400 | 参数校验失败（如用户名已存在、密码太短） |
| 401 | 未认证或 Token 无效/过期 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
