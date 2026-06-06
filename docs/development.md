# InnovOS 开发规范

## 1. 代码风格

### 1.1 Python (后端)

```python
# 导入顺序：标准库 → 第三方库 → 本地模块
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import UserResponse
from app.tasks import TaskRepository

# 类型注解强制要求
def process_task(task_id: int, user: UserResponse) -> dict:
    """函数文档字符串：说明功能和返回值"""
    result = {"id": task_id, "status": "completed"}
    return result
```

**规范要求：**
- 遵循 PEP 8
- 行最大长度 100 字符
- 使用类型注解
- 类名 PascalCase
- 函数/变量名 snake_case

### 1.2 TypeScript (前端)

```typescript
// 导入顺序：React → 第三方库 → 本地模块
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { Task } from '../types/task';

// 类型定义优先
interface TaskInputProps {
  onSubmit: (task: Task) => void;
  initialData?: Partial<Task>;
}

// 组件命名 PascalCase
export const TaskInputPanel: React.FC<TaskInputProps> = ({
  onSubmit,
  initialData,
}) => {
  const [loading, setLoading] = useState(false);
  
  return (
    <div className="glass-panel">
      {/* 组件内容 */}
    </div>
  );
};
```

**规范要求：**
- 使用 TypeScript strict 模式
- 组件文件 ≤200 行
- 强制类型定义，禁止 any
- 命名：组件 PascalCase，函数 camelCase，常量 UPPER_SNAKE
- 使用函数组件 + Hooks
- TailwindCSS 类名排序一致

## 2. Git 工作流

### 2.1 分支策略

```
main          ─── 生产分支，只允许 PR 合并
  ├── develop ─── 开发分支，日常开发合并目标
  │   ├── feature/task-crud  ─── 功能开发
  │   ├── fix/login-timeout  ─── Bug 修复
  │   └── refactor/api-layer ─── 重构
```

### 2.2 提交规范

```
<type>(<scope>): <简短描述>

[可选详细描述]

[可选关闭的 Issue]
```

**类型 (type)：**
- feat: 新功能
- fix: Bug 修复
- refactor: 重构
- style: 代码格式
- docs: 文档
- test: 测试
- chore: 构建/工具

**示例：**
```
feat(tasks): 添加任务分页查询接口

- 支持 page/page_size 参数
- 支持 status 和 category 过滤
- 返回总条数和总页数

Closes #42
```

### 2.3 PR 规范

- 标题格式同提交规范
- 描述包含改动说明和测试方法
- 关联 Issue 和 Project
- 至少 1 人 Review 后合并

## 3. 代码审查要点

### 3.1 后端审查
| 检查项 | 说明 |
|--------|------|
| 类型注解 | 函数参数和返回值是否完整 |
| 异常处理 | 是否 catch 并转义为用户友好错误 |
| SQL 注入 | 是否使用参数化查询 |
| 数据隔离 | 是否按 user_id 过滤 |
| 事务管理 | 多表操作是否使用事务 |
| 性能 | N+1 查询、缺少索引 |

### 3.2 前端审查
| 检查项 | 说明 |
|--------|------|
| Type 安全 | 是否有 any 类型 |
| 状态管理 | loading/error 状态是否处理 |
| 内存泄漏 | useEffect 是否清理订阅 |
| 组件粒度 | 是否过重或过碎片 |
| 错误处理 | API 错误是否展示给用户 |

## 4. 组件规范

### Zustand Store 规范

```typescript
interface TaskState {
  // 状态
  tasks: Task[];
  loading: boolean;
  error: string | null;
  
  // 操作
  fetchTasks: () => Promise<void>;
  createTask: (data: TaskCreate) => Promise<void>;
  clearError: () => void;
}

// try-catch 必须重置 loading
const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  loading: false,
  error: null,
  
  fetchTasks: async () => {
    set({ loading: true, error: null });
    try {
      const tasks = await api.getTasks();
      set({ tasks, loading: false });
    } catch (e) {
      set({ error: e.message, loading: false });
    }
  },
}));
```

## 6. 环境配置

### 6.1 环境变量

```bash
# .env.example
DATABASE_URL=sqlite:///InnovOS_ACCOUNTS.db
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
JWT_EXPIRE_HOURS=24
CORS_ORIGINS=http://localhost:5173
CUDA_ENABLED=false
LOG_LEVEL=INFO
```

### 6.2 环境划分

| 环境 | 数据库 | 日志级别 | 调试模式 |
|------|--------|----------|----------|
| 开发 | SQLite | DEBUG | 开启 |
| 测试 | SQLite 测试库 | INFO | 开启 |
| 生产 | PostgreSQL | WARNING | 关闭 |

## 7. 测试规范

### 7.1 测试框架

| 层级 | 框架 | 说明 |
|------|------|------|
| 后端单元测试 | pytest | 函数级别测试 |
| 后端接口测试 | pytest + httpx | API 端点测试 |
| 前端单元测试 | Vitest | 组件/Hook 测试 |
| 前端集成测试 | Vitest + React Testing Library | 页面级别测试 |

### 7.2 测试文件结构

```
backend/tests/
├── conftest.py           # 测试配置和 fixtures
├── test_auth.py          # 认证模块测试
├── test_keys.py          # Key 管理测试
├── test_analysis.py      # 分析模块测试
└── test_algorithm/       # 算法模块测试
    ├── test_zr_ipm.py
    └── test_key_manager.py

frontend/src/
├── __tests__/
│   ├── components/       # 组件测试
│   ├── features/         # 功能测试
│   └── api/              # API 测试
└── *.test.tsx            # 测试文件就近放置
```

### 7.3 测试命名规范

```python
# 后端：test_功能_场景_预期结果
def test_create_key_valid_input_returns_success():
def test_create_key_missing_api_key_returns_422():
def test_decrypt_key_wrong_key_returns_original():
```

```typescript
// 前端：describe(功能) + it(场景)
describe('KeyManagementPage', () => {
  it('should display empty state when no keys', () => {});
  it('should open create modal on button click', () => {});
});
```

### 7.4 测试覆盖率要求

| 模块 | 最低覆盖率 | 说明 |
|------|-----------|------|
| 认证 | 90% | 安全相关，高覆盖 |
| Key 管理 | 85% | 核心功能 |
| AI 调用 | 80% | 依赖外部服务，mock 测试 |
| UI 组件 | 70% | 重点测试交互逻辑 |

### 7.5 运行测试

```bash
# 后端测试
cd backend
pytest tests/ -v --cov=app --cov-report=html

# 前端测试
cd frontend
npm run test -- --coverage

# 全量测试
make test
```
