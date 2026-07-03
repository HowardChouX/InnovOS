# PatentHub API 集成方案

## 一、现有架构分析

当前InnovOS专利检索流程：
```
前端 → 后端API → 专利数据库（本地PostgreSQL）
```

问题：
- 本地专利数据库可能过时
- 更新维护成本高
- 数据量有限

## 二、集成方案设计

### 方案A：替代模式（推荐）

```
前端 → 后端API → PatentHub API → 云端专利库
                    ↓
              本地缓存（常用专利）
```

优势：
- ✅ 数据实时更新
- ✅ 全球6500万+专利库
- ✅ 无需维护本地数据
- ✅ 免费版可立即使用

### 方案B：混合模式

```
前端 → 后端API → PatentHub API + 本地数据库（并行）
                    ↓
              智能路由（根据专利来源自动选择）
```

优势：
- ✅ 兼容现有数据
- ✅ 渐进式迁移
- ❌ 架构复杂度高

**推荐方案A**，简单直接。

## 三、技术实现

### 1. 后端模块创建

```
backend/app/
├── algorithm/
│   ├── patent_hub/
│   │   ├── __init__.py
│   │   ├── client.py           # PatentHub API客户端
│   │   ├── models.py           # 数据模型
│   │   └── exceptions.py       # 异常处理
│   └── patent_service.py       # 统一专利服务接口
```

### 2. 核心API封装

```python
# client.py
class PatentHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://www.patenthub.cn/api"

    def search(self, query: str, page: int = 1, page_size: int = 10) -> dict:
        """专利搜索"""
        # GET /api/s

    def get_patent(self, patent_id: str) -> dict:
        """获取专利基本信息"""
        # GET /api/patent/base

    def get_claims(self, patent_id: str) -> dict:
        """获取权利要求"""
        # GET /api/patent/claims

    def get_description(self, patent_id: str) -> dict:
        """获取说明书"""
        # GET /api/patent/desc
```

### 3. 前端搜索流程

```
用户输入关键词
     ↓
调用 /api/patent/search
     ↓
返回专利列表（分页）
     ↓
用户点击某个专利
     ↓
调用 /api/patent/detail
     ↓
展示：基本信息 + 权利要求 + 说明书
```

## 四、API接口设计

### 现有接口（保持不变）
```
GET  /api/patents          - 本地专利列表（可选）
POST /api/patents          - 创建专利（可选）
```

### 新增接口
```
GET  /api/patenthub/search     - PatentHub搜索
GET  /api/patenthub/{id}       - PatentHub专利详情
GET  /api/patenthub/{id}/claims  - 权利要求
GET  /api/patenthub/{id}/desc   - 说明书
GET  /api/patenthub/{id}/citing - 引用关系
```

## 五、数据库设计（可选）

```sql
-- 本地缓存表（可选）
CREATE TABLE patent_cache (
    id SERIAL PRIMARY KEY,
    patent_number TEXT UNIQUE NOT NULL,
    title TEXT,
    applicant TEXT,
    application_date DATE,
    legal_status TEXT,
    claims TEXT,
    description TEXT,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP  -- 缓存过期时间
);
```

优势：
- 高频访问的专利缓存
- 减少API调用（免费版限制）
- 离线访问支持

## 六、配置文件

```python
# .env
PATENT_HUB_ENABLED=true
PATENT_HUB_TOKEN=6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc
PATENT_HUB_BASE_URL=https://www.patenthub.cn/api
PATENT_CACHE_TTL=86400  # 缓存24小时
PATENT_SEARCH_PAGE_SIZE=10  # 默认每页10条
```

## 七、使用场景

### 场景1：InnovOS智能分析流程

```
用户输入问题："手机电池发热问题"
     ↓
触发AI分析 → 提取技术关键词
     ↓
调用PatentHub搜索 → 获取相关专利
     ↓
返回：专利列表 + 摘要 + 分析
     ↓
AI生成创新方案
```

### 场景2：专利检索页面

```
用户在检索页面输入关键词
     ↓
实时搜索PatentHub
     ↓
展示：专利列表（标题、申请人、日期、状态）
     ↓
用户点击某个专利
     ↓
展示：完整详情（权利要求、说明书、引用关系）
```

## 八、实施步骤

### Phase 1（1-2天）：基础集成
- [ ] 创建PatentHub客户端模块
- [ ] 实现搜索、详情、权利要求、说明书接口
- [ ] 编写单元测试

### Phase 2（3-4天）：后端API
- [ ] 创建专利检索路由
- [ ] 实现本地缓存逻辑
- [ ] 错误处理和限流

### Phase 3（5-7天）：前端集成
- [ ] 改造专利检索页面
- [ ] 实现实时搜索
- [ ] 展示专利详情（权利要求、说明书）

### Phase 4（8-10天）：优化
- [ ] 缓存机制
- [ ] 搜索结果过滤
- [ ] 性能优化

## 九、费用估算

### 免费版（现在）
- 50次/天
- 适合开发测试

### 个人版（288元/年）
- 1000次/天
- 适合生产环境（小规模）

### 专业版（980元/年）
- 不限次数
- 适合生产环境（中大规模）

## 十、风险控制

1. **API调用限制**
   - 实现本地缓存
   - 控制调用频率
   - 监控使用量

2. **网络延迟**
   - 异步调用
   - 请求超时设置（30s）
   - 失败重试机制

3. **数据一致性**
   - 缓存过期策略
   - 定期更新检查

## 十一、预期收益

### 对InnovOS
- ✅ 全球6500万+实时专利数据
- ✅ 无需维护本地数据库
- ✅ 开发成本低（集成简单）
- ✅ 免费版可立即使用

### 对用户
- ✅ 实时搜索最新专利
- ✅ 丰富的专利详情
- ✅ 更好的创新分析结果

## 十二、下一步

你想现在开始实施吗？我可以：

1. **立即开始Phase 1** - 创建PatentHub客户端模块
2. **先做原型** - 创建一个最小可工作的搜索功能
3. **其他** - 你有其他想法

如何开始？
