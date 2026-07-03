# 问题建模页面重新设计方案

## 当前问题

1. **静态符号过多** - 占用空间但没有交互价值
2. **信息展示不够清晰** - 用户难以理解分析结果
3. **与专利检索的关联性弱** - 无法优化搜索相关性

## 重新设计目标

1. **删除静态符号** - 简化界面
2. **创建对话式界面** - 让用户理解每一步的分析
3. **优化专利检索输入** - 确保用户能指导搜索方向

## 新界面设计

### 布局结构

```
┌─────────────────────────────────────────┐
│ 📋 问题分析结果                    编辑   │
├─────────────────────────────────────────┤
│                                         │
│ 🔍 核心问题                              │
│ ┌─────────────────────────────────────┐ │
│ │ 手机发热问题                         │ │
│ │ 电池 → 外壳 → 用户                  │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 🔬 问题分解                              │
│ ┌─────────────────────────────────────┐ │
│ │ 1. 电池充电发热                      │ │
│ │ 2. 保护壳阻碍散热                    │ │
│ │ 3. 用户感知过热                      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 💡 创新方向（请评分）                    │
│ ┌─────────────────────────────────────┐ │
│ │ 1. 电池热管理系统优化         ⭐⭐⭐⭐⭐ │ │
│ │    ├─ 来源: 热力学分析               │ │
│ │    ├─ 原理: 主动冷却技术             │ │
│ │    └─ 期望: 降低峰值温度30%         │ │
│ │                                     │ │
│ │ 2. 散热材料创新               ⭐⭐⭐⭐  │ │
│ │    ├─ 来源: 材料科学                 │ │
│ │    ├─ 原理: 高导热复合材料           │ │
│ │    └─ 期望: 提升热传导效率           │ │
│ │                                     │ │
│ │ 3. 电池结构改进               ⭐⭐⭐   │ │
│ │    ├─ 来源: 结构工程                 │ │
│ │    ├─ 原理: 分布式散热设计           │ │
│ │    └─ 期望: 均匀化热量分布           │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 📊 分析说明                              │
│ ┌─────────────────────────────────────┐ │
│ │ • 绿色标签 = 专利检索关键词          │ │
│ │ • 评分越高 → 检索越优先              │ │
│ │ • 点击方向可修改搜索词               │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [确认并进入专利检索]                     │
│                                         │
└─────────────────────────────────────────┘
```

### 交互设计

#### 1. 评分交互
- 每个创新方向旁边有5星评分
- 用户点击星星进行评分
- 评分实时保存

#### 2. 搜索词编辑（新增功能）
- 每个创新方向可点击"编辑搜索词"
- 弹出输入框让用户修改
- 修改后用于专利检索

#### 3. 确认逻辑
- 用户必须对所有创新方向评分
- 评分后点击"确认并进入专利检索"
- 系统用评分高的方向优先检索

## 代码实现

### 1. 删除静态符号

删除以下静态元素：
- "问题建模"图标
- "构建问题模型，识别核心冲突"描述
- 空白占位符

### 2. 新增交互功能

```typescript
// 创新方向可编辑
interface Innovation {
  id: string;
  description: string;
  search_query?: string;     // 新增：用户可修改的搜索词
  principle: string;
  expected_effect: string;
  user_rating: number | null;
}
```

### 3. 优化UI组件

```tsx
// 创新方向卡片
function InnovationCard({ innovation, onRate, onEditQuery }) {
  return (
    <div className="innovation-card">
      <div className="card-header">
        <span className="title">{innovation.description}</span>
        <StarInput 
          value={innovation.user_rating} 
          onChange={(v) => onRate(innovation.id, v)} 
        />
      </div>
      
      <div className="card-body">
        <div className="tags">
          <span className="source">{innovation.source_analyzer}</span>
          <span className="principle">{innovation.principle}</span>
        </div>
        
        <div className="description">{innovation.expected_effect}</div>
        
        {/* 新增：搜索词编辑 */}
        <div className="search-query">
          <span className="label">检索关键词：</span>
          <input 
            value={innovation.search_query || innovation.description}
            onChange={(e) => onEditQuery(innovation.id, e.target.value)}
          />
          <span className="hint">（可修改，用于专利检索）</span>
        </div>
      </div>
    </div>
  );
}
```

## PatentHub API 集成

### 搜索逻辑

```python
def search_patents_for_innovations(innovations, ratings):
    """根据创新方向和评分搜索专利"""
    
    # 按评分排序（高分优先）
    sorted_innovations = sorted(
        innovations,
        key=lambda x: x['user_rating'] or 0,
        reverse=True
    )
    
    # 收集搜索查询
    search_queries = []
    for inn in sorted_innovations:
        # 优先使用用户修改的搜索词
        query = inn.get('search_query') or inn['description']
        search_queries.append({
            'query': query,
            'innovation_id': inn['id'],
            'rating': inn['user_rating']
        })
    
    # 执行PatentHub搜索
    results = []
    for sq in search_queries:
        patenthub_results = patenthub_client.search(
            q=sq['query'],
            page_size=10
        )
        
        # 标记来源
        for patent in patenthub_results:
            patent['source_innovation'] = sq['innovation_id']
            patent['source_rating'] = sq['rating']
        
        results.extend(patenthub_results)
    
    return results
```

## 实施步骤

### Phase 1：删除静态符号
1. 移除图标和描述
2. 简化布局
3. 保持评分功能

### Phase 2：创建交互设计
1. 添加搜索词编辑功能
2. 优化卡片样式
3. 添加提示信息

### Phase 3：集成PatentHub
1. 用评分高的方向优先检索
2. 支持用户自定义搜索词
3. 显示检索结果来源

## 预期效果

### 对用户
- ✅ 更清晰地理解问题分析结果
- ✅ 能控制专利检索的方向
- ✅ 看到每个创新方向的检索结果

### 对专利检索
- ✅ 搜索相关性提高（因为用户指导）
- ✅ 结果更符合用户需求
- ✅ 减少无效检索

## 下一步

你想现在就开始实施吗？我可以：

1. **立即开始Phase 1** - 删除静态符号，简化界面
2. **先设计原型** - 创建新的交互式设计
3. **其他** - 你有其他想法

如何开始？
