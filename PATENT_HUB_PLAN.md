# PatentHub API 集成策略

## 当前状态（7天免费体验）

### 可用接口
- ✓ 搜索接口 `/api/s` - 核心搜索功能
- ✓ 基本信息接口 `/api/patent/base` - 单专利详情
- ✓ 权利要求接口 `/api/patent/claims` - 权利要求全文
- ✓ 说明书接口 `/api/patent/desc` - 说明书全文

### 受限接口（需要付费）
- ✗ 详细信息接口 `/api/patent/detail` - code=208
- ✗ 统计分析接口 `/api/ration` - code=208
- 可能还有其他限制（每日调用量等）

## 设计方案：优雅降级 + 多源融合

### 核心思路
1. **本地数据库** 作为主要数据源（现有专利）
2. **PatentHub API** 作为补充数据源（新专利）
3. **配置开关** 可以切换/融合两者
4. **受限接口** 自动降级为替代方案

### 架构设计

```
┌─────────────────────────────────────────┐
│        PatentService (抽象层)           │
├─────────────────────────────────────────┤
│  - search()                            │
│  - get_detail()                        │
│  - get_claims()                        │
│  - get_description()                   │
│  - analyze()                           │
└──────────┬──────────┬──────────────────┘
           │          │
     ┌─────┴─────┐   ┌┴──────────┐
     │ LocalDB   │   │ PatentHub │
     │ (现有)    │   │   API     │
     └───────────┘   └───────────┘
           │                │
           └────────┬───────┘
                    │
              ┌─────┴─────┐
              │  Results   │
              │  Merge     │
              └───────────┘
```

### 降级策略

| 接口 | 状态 | 降级方案 |
|------|------|---------|
| search | ✓ 可用 | 正常调用API |
| patent/base | ✓ 可用 | 正常调用API |
| patent/claims | ✓ 可用 | 正常调用API |
| patent/desc | ✓ 可用 | 正常调用API |
| patent/detail | ✗ 受限 | 用 base+claims+desc 组合 |
| ration | ✗ 受限 | 本地统计 或 不可用 |
| 图片/PDF | ? | 正常调用（通常不限制）|

### 实现步骤

1. **Phase 1: 基础集成**（第1-2天）
   - 创建PatentHub客户端
   - 集成搜索和基本信息接口
   - 验证基础功能

2. **Phase 2: 降级逻辑**（第3-4天）
   - 实现detail降级为 base+claims+desc
   - 处理错误和限流
   - 缓存机制

3. **Phase 3: 融合优化**（第5-7天）
   - 本地数据库 + API融合
   - 智能路由（根据权限自动选择）
   - 性能优化

### 代码结构

```
backend/app/
├── algorithm/
│   ├── patent_hub_client.py      # PatentHub API客户端
│   └── patent_service.py         # 统一专利服务接口
├── api/
│   └── patents.py                # 专利API路由（现有）
└── config/
    └── settings.py               # 添加PATENT_HUB配置
```

## 配置设计

```python
# .env
PATENT_HUB_ENABLED=true
PATENT_HUB_TOKEN=6457d6bbc0d16ffcae52abb9d8f763fa3e09c4fc
PATENT_HUB_BASE_URL=https://www.patenthub.cn/api
PATENT_SOURCE=both  # local|api|both
```

## 下一步

1. 现在就开始Phase 1，创建PatentHub客户端？
2. 还是先测试一下7天内哪些接口真正可用？
3. 或者你有其他想法？

你更倾向哪个方案？
