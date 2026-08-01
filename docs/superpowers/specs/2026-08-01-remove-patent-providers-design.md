# 移除现有外部专利接口设计

日期：2026-08-01

## 1. 背景

InnovOS 当前同时包含 CNIPR 和 PatentHub 两套外部专利接口实现。它们引入供应商配置、认证客户端、远程搜索与详情调用、外部搜索优化逻辑以及对应测试。CNIPR 配置未设置时，Docker Compose 会在每次解析配置时输出环境变量警告。

本次变更将彻底删除这两套外部接口。未来需要外部专利数据时，重新根据届时的供应商和业务需求设计，不保留当前实现的兼容层、Provider 抽象、禁用开关或占位代码。

## 2. 目标

1. 删除 CNIPR 与 PatentHub 的客户端、认证、搜索、详情和分析实现。
2. 删除只服务于现有外部供应商的搜索优化逻辑。
3. 删除所有现有外部专利供应商配置及 Docker Compose 环境变量。
4. 保留本地专利库、专利向量、后台管理、前端页面和工作流专利检索阶段。
5. 将专利搜索和详情查询稳定收敛到本地 PostgreSQL 数据。
6. 清理所有无调用方代码、测试、类型、注释和文档引用。
7. 消除 Docker Compose 中 CNIPR 环境变量未设置的警告。

## 3. 非目标

1. 不删除 `patents` 或 `patent_vectors` 表。
2. 不删除现有专利数据或 `backend/storage/patents/` 文件。
3. 不删除后台专利上传、PDF 解析、结构化提取或向量化能力。
4. 不删除前台专利检索、专利转化页面或工作流专利检索阶段。
5. 不设计新的外部专利 Provider 协议、注册表、配置选择或降级链。
6. 不为历史外部接口参数保留兼容垫片。
7. 不删除 `httpx` 依赖，因为项目其他网络调用仍在使用它。

## 4. 删除范围

### 4.1 后端文件

删除以下只服务于现有外部接口的文件：

- `backend/app/algorithm/cnipr_client.py`
- `backend/app/algorithm/patent_hub_client.py`
- `backend/app/algorithm/patent_search_optimizer.py`

### 4.2 配置

从 Pydantic Settings、Docker Compose、示例环境文件及相关文档中删除：

- `PATENT_HUB_TOKEN`
- `CNIPR_CLIENT_ID`
- `CNIPR_CLIENT_SECRET`
- `CNIPR_USERNAME`
- `CNIPR_PASSWORD`

本地未跟踪 `.env` 中若存在这些键，也应由开发者删除；实现代码不再读取它们。

### 4.3 分支、类型与文案

删除：

- `source=patenthub` 和 `source=cnipr` 查询分支。
- 搜索结果中的供应商 `source` 字段。
- 前端 `Patent.source` 的 `patenthub | cnipr | local` 联合类型及无调用方字段。
- “外部优先、本地降级”“PatentHub 主数据源”等过时注释、日志和错误消息。
- CNIPR、PatentHub、搜索优化器相关测试、Mock 和 fixture。

## 5. 保留范围

保留并确保继续工作的能力：

- PostgreSQL `patents` 表及现有数据。
- `patent_vectors` 表、向量索引和本地向量搜索。
- `backend/app/algorithm/patent_service.py`，但改为纯本地专利业务服务。
- `backend/app/algorithm/patent_search_engine.py`。
- `backend/app/algorithm/patent_extractor.py`。
- `backend/app/api/patents.py`。
- `backend/app/api/admin/patent_db.py`。
- 前台专利检索与专利转化页面。
- 后台专利库管理页面。
- 工作流中的专利检索阶段及现有结果展示。
- `backend/storage/patents/` 中的本地文件。

## 6. 本地数据流

变更后的专利数据流为：

```text
前端专利页面 / 工作流
          ↓
/api/patents 或 patent_service.py
          ↓
PostgreSQL patents / patent_vectors
```

`patent_service.py` 不再尝试远程请求，也不包含供应商选择、认证、远程失败降级或供应商来源判断。未来接入新接口时重新设计，不以本次本地服务结构作为必须兼容的 Provider 合同。

## 7. API 行为

### 7.1 搜索

保留：

```http
GET /api/patents/search
```

支持参数：

- `q`
- `ipc_code`
- `applicant`
- `sort_by`
- `order`
- `page`
- `page_size`

删除 `source` 参数。搜索全部基于本地 SQL，并正确应用关键词、IPC、申请人、排序和分页。

响应继续包含：

- `data`
- `total`
- `page`
- `page_size`
- `total_pages`
- `message`
- `code`

单条专利结果不再包含供应商 `source` 字段。

### 7.2 详情

保留：

```http
GET /api/patents/detail/{pid}
```

仅从本地数据库按内部 ID、专利号或公开号查询。未找到时返回中文 404；数据库异常写入服务端日志，对客户端返回中文通用错误，不回传原始数据库异常。

### 7.3 工作流

工作流的 `patent_search()` 直接使用本地专利数据：

- 根据创新方向和任务描述构造本地关键词。
- 查询本地专利并生成 `patents`、`direction_patents` 和 `total_found`。
- 删除供应商 `source` 返回值及调用方日志。
- 无匹配结果时返回空结果，工作流继续执行。

## 8. 本地检索约束

1. 所有 SQL 使用参数化查询。
2. 动态排序列和排序方向使用白名单，禁止直接拼接客户端输入。
3. 数据库连接使用 `with db_session() as db:`，不新增 `get_db()` 手动关闭模式。
4. 分页总数由与列表相同的筛选条件计算。
5. 本地专利字段统一映射由服务层负责，避免 API 路由和工作流重复转换。
6. 用户可见错误消息保持中文。

## 9. 测试设计

删除：

- CNIPR 客户端测试。
- PatentHub 客户端测试。
- 外部搜索优化器测试。
- 外部失败后降级本地的测试。

新增或改写：

1. 本地关键词检索。
2. IPC 筛选。
3. 申请人筛选。
4. 排序列、排序方向白名单。
5. 正确分页及总数。
6. 空查询返回本地分页列表。
7. 本地详情按内部 ID、专利号和公开号查询。
8. 详情未找到返回 404。
9. 工作流仅调用本地检索。
10. 工作流空结果可继续。
11. 数据库异常不向客户端泄漏原始异常。
12. 搜索接口不再暴露 `source` 参数和字段。

保留并运行现有专利向量、专利上传和解析测试。

## 10. 文档与清理

同步更新 `AGENTS.md` 和相关文档，明确专利功能当前只使用本地数据库。全局检查代码、配置和测试，确保不存在以下现有供应商符号：

- `CNIPR`
- `PATENT_HUB_TOKEN`
- `PatentHub`
- `patenthub`
- `cnipr`

设计文档和历史迁移记录可以描述已删除内容；生产代码、运行配置、活动文档和测试不得继续引用现有供应商实现。

## 11. 验收

执行：

```bash
docker compose config --quiet
make quality
```

启动验证：

```bash
docker compose up -d
docker compose ps -a
curl -fsS http://localhost:8000/api/health
```

验收标准：

1. Docker Compose 不再输出 CNIPR 环境变量未设置警告。
2. 生产代码和运行配置中不存在 CNIPR 或 PatentHub 实现。
3. Backend 与 Frontend 正常运行。
4. 本地专利搜索、筛选、排序、分页和详情正常。
5. 后台专利管理、PDF 导入、向量检索和工作流专利阶段正常。
6. `make quality` 全部门禁通过。

## 12. 数据安全与回滚

本次不包含删除表、删除数据或数据迁移。`docker compose down` 不使用 `-v`，避免删除命名卷。代码回滚可恢复旧接口实现，但已删除的供应商凭据不会由代码或文档保存。
