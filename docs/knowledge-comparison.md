# Cherry Studio vs InnovOS 知识库对比文档

## 后端对比

### 1. KnowledgeBaseService
- cherry-studio: 使用 Drizzle ORM，有完整的 CRUD 操作
- InnovOS: 使用原生 SQL，功能类似但缺少一些方法

### 2. KnowledgeItemService
- cherry-studio: 有完整的 CRUD、子树操作、状态管理、容器协调
- InnovOS: 只有基本的 CRUD，缺少子树操作和容器协调

### 3. KnowledgeOrchestrationService
- cherry-studio: 完整的编排层，有 IPC 处理器、作业管理、崩溃恢复
- InnovOS: 简单的编排层，缺少作业管理和崩溃恢复

### 4. KnowledgeWorkflowService
- cherry-studio: 完整的工作流服务，有项目调度、文件处理检查、索引调度
- InnovOS: 缺少这个服务

### 5. KnowledgeLockManager
- cherry-studio: 使用 async-mutex，有完整的锁管理
- InnovOS: 使用简单的 asyncio.Lock

### 6. Job Handlers
- cherry-studio: 5个作业处理器 (prepare-root, index-documents, check-file-processing-result, delete-subtree, reindex-subtree)
- InnovOS: 缺少作业系统

### 7. Vector Store
- cherry-studio: 使用 LibSQL 向量存储
- InnovOS: 使用 numpy 内存存储

### 8. Rerank
- cherry-studio: 支持多种重排适配器
- InnovOS: 缺少重排系统

## 前端对比

### 1. KnowledgePageProvider
- cherry-studio: 使用 React Context，完整的状态管理
- InnovOS: 使用 Zustand store

### 2. Navigator
- cherry-studio: 支持分组、搜索、拖拽调整宽度
- InnovOS: 基本的导航器

### 3. Detail
- cherry-studio: 支持搜索、配置、重排测试
- InnovOS: 基本的详情页

### 4. Dialog
- cherry-studio: 支持创建、重命名、删除对话框
- InnovOS: 基本的对话框

### 5. Hooks
- cherry-studio: useKnowledgeBase, useKnowledgeItems, SWR 轮询
- InnovOS: useKnowledgeStore (Zustand)

## 需要复现的核心功能

1. **后端**: KnowledgeItemService 的子树操作、容器协调、状态管理
2. **后端**: KnowledgeOrchestrationService 的作业管理、崩溃恢复
3. **后端**: KnowledgeWorkflowService 的工作流
4. **后端**: Job Handlers (至少 delete-subtree 和 reindex-subtree)
5. **前端**: KnowledgePageProvider (Context 模式)
6. **前端**: Navigator 的分组和搜索
7. **前端**: Detail 的搜索和配置
8. **前端**: Hooks (useKnowledgeBase, useKnowledgeItems)

## 实施计划

### 阶段 1: 后端核心服务
1. 更新 KnowledgeItemService 添加子树操作和容器协调
2. 更新 KnowledgeOrchestrationService 添加作业管理和崩溃恢复
3. 创建 KnowledgeWorkflowService
4. 创建 KnowledgeLockManager

### 阶段 2: 后端作业系统
1. 创建 delete-subtree 作业处理器
2. 创建 reindex-subtree 作业处理器
3. 创建 index-documents 作业处理器

### 阶段 3: 前端核心组件
1. 创建 KnowledgePageProvider (Context)
2. 更新 Navigator 支持分组和搜索
3. 更新 Detail 支持搜索和配置
4. 创建 Hooks (useKnowledgeBase, useKnowledgeItems)

### 阶段 4: 验证
1. 验证后端 API
2. 验证前端构建
3. 验证功能完整性
