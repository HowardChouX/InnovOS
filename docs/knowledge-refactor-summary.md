# 知识库重构总结

## 重构目标

参考 cherry-studio 的架构设计，重构 InnovOS 知识库模块，提升代码质量、类型安全和可维护性。

## 主要变更

### 1. 数据模型 (`app/models/knowledge.py`)

**新增内容：**
- 使用 Pydantic 定义完整类型系统
- 知识项类型枚举：`file`, `url`, `note`, `directory`
- 知识项状态机：`idle`, `preparing`, `processing`, `reading`, `embedding`, `completed`, `failed`, `deleting`
- 知识库状态：`completed`, `failed`
- 错误码：`missing_embedding_model`
- 搜索模式：`default`, `bm25`, `hybrid`
- 数据验证规则

**参考 cherry-studio：**
- `src/shared/data/types/knowledge.ts` - 类型定义
- `src/main/data/db/schemas/knowledge.ts` - 数据库 schema

### 2. 服务层 (`app/services/knowledge_service_v3.py`)

**新增内容：**
- `KnowledgeBaseService` - 知识库数据持久化
- `KnowledgeItemService` - 知识项数据持久化
- 完整的 CRUD 操作
- 状态管理
- 关联查询（item count）

**参考 cherry-studio：**
- `src/main/data/services/KnowledgeBaseService.ts`
- `src/main/data/services/KnowledgeItemService.ts`

### 3. 编排层 (`app/services/knowledge_orchestration.py`)

**新增内容：**
- `KnowledgeOrchestrationService` - 知识库工作流协调
- `KnowledgeLockManager` - 同库变更序列化
- 知识项生命周期管理
- 异步任务处理
- 搜索协调

**参考 cherry-studio：**
- `src/main/services/knowledge/KnowledgeOrchestrationService.ts`
- `src/main/services/knowledge/KnowledgeLockManager.ts`

### 4. API 层 (`app/api/knowledge_bases_v2.py`)

**新增内容：**
- RESTful 端点
- 请求/响应验证
- 错误处理
- 分页支持

**参考 cherry-studio：**
- `src/main/data/api/handlers/knowledges.ts`

## 架构对比

### 原架构
```
API → Service → Database (原生 SQL)
```

### 新架构
```
API → OrchestrationService → KnowledgeBaseService/KnowledgeItemService → Database
                    ↓
              LockManager (并发控制)
                    ↓
              VectorStore (向量存储)
```

## 待完成工作

1. **文件处理管道**
   - 实现 `_process_file_item`
   - 实现 `_process_url_item`
   - 实现 `_process_note_item`
   - 实现 `_process_directory_item`

2. **向量存储集成**
   - 对接现有 `VectorStore`
   - 实现向量删除

3. **状态协调**
   - 实现容器项状态从子项状态协调
   - 实现 `reindex_items`

4. **测试**
   - 单元测试
   - 集成测试

## 文件变更列表

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/models/knowledge.py` | 新增 | 数据模型定义 |
| `app/services/knowledge_service_v3.py` | 新增 | 服务层实现 |
| `app/services/knowledge_orchestration.py` | 新增 | 编排层实现 |
| `app/api/knowledge_bases_v2.py` | 新增 | API 层实现 |

## 参考资源

- cherry-studio 知识库架构：`docs/references/knowledge/`
- cherry-studio 类型定义：`src/shared/data/types/knowledge.ts`
- cherry-studio 数据库 schema：`src/main/data/db/schemas/knowledge.ts`
