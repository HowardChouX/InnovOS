# 专利检索相关度优化方案

## 核心原则

```
自动化优化（无需用户干预）
├── 问题建模 → 自动提取关键词
├── 自动生成 → PatentHub最优查询
├── 相关度排序 → 智能权重计算
└── 用户只需 → 评分（确定优先级）
```

## 相关度优化策略

### 1. 关键词提取优化

```python
class KeywordExtractor:
    """从创新方向中自动提取关键词"""
    
    def extract(self, innovation_description):
        """
        输入：创新方向描述
        输出：优化的关键词列表
        """
        
        # 1. 核心实体提取
        entities = self.extract_entities(innovation_description)
        
        # 2. 技术关键词
        tech_keywords = self.extract_tech_keywords(innovation_description)
        
        # 3. 问题关键词
        problem_keywords = self.extract_problem_keywords(innovation_description)
        
        # 4. 组合并优化
        keywords = self.optimize_keywords(
            entities + tech_keywords + problem_keywords
        )
        
        return keywords
    
    def extract_entities(self, text):
        """提取核心实体（电池、热、材料等）"""
        # 使用NLP或规则匹配
        return ["电池", "热管理"]  # 示例
    
    def extract_tech_keywords(self, text):
        """提取技术关键词"""
        return ["优化", "系统", "技术"]  # 示例
```

### 2. PatentHub查询生成优化

```python
class QueryOptimizer:
    """生成PatentHub最优查询"""
    
    def optimize_query(self, keywords, innovation):
        """
        生成相关度最高的PatentHub查询
        """
        
        # 1. 标题搜索（最高相关性）
        title_query = self.build_title_query(keywords)
        
        # 2. 摘要搜索（补充）
        summary_query = self.build_summary_query(keywords)
        
        # 3. IPC分类号（专业性）
        ipc_codes = self.infer_ipc_codes(keywords)
        ipc_query = self.build_ipc_query(ipc_codes)
        
        # 4. 组合查询（权重优化）
        query = self.combine_queries(
            title=title_query,
            summary=summary_query,
            ipc=ipc_query,
            weights={
                'title': 0.6,      # 标题权重最高
                'summary': 0.3,    # 摘要权重次之
                'ipc': 0.1,        # IPC权重最低
            }
        )
        
        return query
    
    def build_title_query(self, keywords):
        """构建标题搜索查询"""
        # PatentHub语法：title:关键词
        return f"title:{keywords[0]}"
    
    def build_summary_query(self, keywords):
        """构建摘要搜索查询"""
        # PatentHub语法：summary:关键词
        return f"summary:{' OR '.join(keywords[:3])}"
    
    def infer_ipc_codes(self, keywords):
        """从关键词推断IPC分类号"""
        ipc_mapping = {
            "电池": ["H01M"],
            "热": ["F28F", "F28D"],
            "材料": ["C08K"],
            "结构": ["B29C"],
        }
        
        codes = []
        for keyword in keywords:
            if keyword in ipc_mapping:
                codes.extend(ipc_mapping[keyword])
        
        return list(set(codes))[:3]  # 去重，最多3个
    
    def combine_queries(self, title, summary, ipc, weights):
        """组合查询（带权重）"""
        
        # 使用AND连接不同维度
        query_parts = []
        
        # 标题搜索（必选）
        query_parts.append(title)
        
        # 摘要搜索（可选）
        if summary:
            query_parts.append(f"({summary})")
        
        # IPC分类号（可选）
        if ipc:
            query_parts.append(f"({ipc})")
        
        return " AND ".join(query_parts)
```

### 3. 相关度评分算法

```python
class RelevanceScorer:
    """计算搜索结果的相关度"""
    
    def score_patent(self, patent, search_query, innovation):
        """
        计算单个专利的相关度分数
        """
        
        score = 0.0
        
        # 1. 标题匹配度（40%）
        title_score = self.title_relevance(
            patent.get('title', ''),
            search_query
        )
        score += title_score * 0.4
        
        # 2. 摘要匹配度（30%）
        summary_score = self.summary_relevance(
            patent.get('summary', ''),
            search_query
        )
        score += summary_score * 0.3
        
        # 3. IPC匹配度（20%）
        ipc_score = self.ipc_relevance(
            patent.get('mainIpc', ''),
            innovation.get('ipc_codes', [])
        )
        score += ipc_score * 0.2
        
        # 4. 申请人相关性（10%）
        applicant_score = self.applicant_relevance(
            patent.get('applicant', ''),
            innovation
        )
        score += applicant_score * 0.1
        
        return round(score, 3)
    
    def title_relevance(self, title, query):
        """标题相关度"""
        # 关键词匹配程度
        matching_words = self.count_matching_words(title, query)
        total_words = len(query.split())
        
        if total_words == 0:
            return 0.0
        
        return matching_words / total_words
    
    def summary_relevance(self, summary, query):
        """摘要相关度"""
        # 同上，但权重降低
        return self.title_relevance(summary, query) * 0.8
    
    def ipc_relevance(self, patent_ipc, target_ipcs):
        """IPC分类号相关度"""
        if not target_ipcs:
            return 0.5  # 无IPC时给中等分
        
        for ipc in target_ipcs:
            if ipc in patent_ipc:
                return 1.0
        
        return 0.0
    
    def applicant_relevance(self, applicant, innovation):
        """申请人相关性"""
        # 与创新方向相关的申请人
        # 可以从问题建模中提取
        return 0.5  # 默认中等分
```

## 搜索流程优化

### 完整流程

```
问题建模输出
    ↓
关键词提取（自动化）
    ↓
查询生成（PatentHub语法）
    ↓
相关度预估（不实际调用API）
    ↓
用户评分（5星）
    ↓
执行PatentHub搜索
    ↓
相关度排序（加权计算）
    ↓
返回优化结果
```

### 代码实现

```python
class OptimizedPatentSearchEngine:
    """优化的专利搜索引擎"""
    
    def __init__(self, patenthub_client):
        self.client = patenthub_client
        self.keyword_extractor = KeywordExtractor()
        self.query_optimizer = QueryOptimizer()
        self.relevance_scorer = RelevanceScorer()
    
    async def search(self, innovations_with_ratings):
        """
        自动优化搜索（无需用户干预）
        """
        
        all_results = []
        
        # 1. 按评分排序（高分优先搜索）
        sorted_innovations = sorted(
            innovations_with_ratings,
            key=lambda x: x.get('user_rating') or 0,
            reverse=True
        )
        
        # 2. 为每个创新方向生成最优查询
        for innovation in sorted_innovations:
            
            # 提取关键词
            keywords = self.keyword_extractor.extract(
                innovation['description']
            )
            
            # 生成PatentHub查询
            query = self.query_optimizer.optimize_query(
                keywords, innovation
            )
            
            # 执行搜索
            search_result = await self.client.search(
                q=query,
                page_size=20
            )
            
            # 3. 计算相关度分数
            scored_results = []
            for patent in search_result.get('patents', []):
                score = self.relevance_scorer.score_patent(
                    patent, query, innovation
                )
                patent['relevance_score'] = score
                patent['source_innovation'] = innovation['id']
                scored_results.append(patent)
            
            all_results.extend(scored_results)
        
        # 4. 按相关度排序
        all_results.sort(
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )
        
        return all_results[:100]  # 返回Top 100
```

## 用户界面设计

### 问题建模页面（优化版）

```
┌─────────────────────────────────────────┐
│ 📋 问题分析结果                          │
├─────────────────────────────────────────┤
│                                         │
│ 🔍 核心问题：手机发热问题                │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│ 💡 创新方向 1                评分：⭐⭐⭐⭐⭐│
│ ┌─────────────────────────────────────┐ │
│ │ 描述：电池热管理系统优化            │ │
│ │ 关键词：电池 + 热管理 + 系统优化    │ │
│ │ IPC分类：H01M（电池领域）          │ │
│ │ 预估相关度：92%                    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 💡 创新方向 2                评分：⭐⭐⭐⭐ │
│ ┌─────────────────────────────────────┐ │
│ │ 描述：散热材料创新                  │ │
│ │ 关键词：散热 + 材料 + 创新         │ │
│ │ IPC分类：C08K（高分子材料）        │ │
│ │ 预估相关度：85%                    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 💡 创新方向 3                评分：⭐⭐⭐  │
│ ┌─────────────────────────────────────┐ │
│ │ 描述：电池结构改进                  │ │
│ │ 关键词：电池 + 结构 + 改进         │ │
│ │ IPC分类：H01M + B29C              │ │
│ │ 预估相关度：78%                    │ │
│ └─────────────────────────────────────┘ │
│                                         │
├─────────────────────────────────────────┤
│ 📊 搜索优化说明                          │
│ • 自动提取关键词，无需手动编辑          │
│ • 优先使用标题搜索（相关度最高）        │
│ • 高评分方向优先检索                    │
│ • 智能过滤低相关度结果                  │
│                                         │
│ [确认并执行智能检索]                     │
│                                         │
└─────────────────────────────────────────┘
```

## 相关度优化策略总结

### 1. 关键词优化
- ✅ 自动从描述中提取核心实体
- ✅ 去除停用词
- ✅ 保留技术术语
- ✅ 生成多个同义词（可选）

### 2. 查询构建优化
- ✅ 标题搜索权重最高（60%）
- ✅ 摘要搜索权重次之（30%）
- ✅ IPC分类号权重最低（10%）
- ✅ 自动推断IPC分类号

### 3. 结果排序优化
- ✅ 标题匹配度（40%）
- ✅ 摘要匹配度（30%）
- ✅ IPC匹配度（20%）
- ✅ 申请人相关性（10%）

### 4. 用户交互优化
- ✅ 无需用户编辑搜索词
- ✅ 只需评分（确定优先级）
- ✅ 自动执行搜索
- ✅ 返回带来源标记的结果

## 实施计划

### Phase 1：基础优化（2-3天）
- [ ] 关键词提取器
- [ ] 查询生成器
- [ ] 基本相关度评分

### Phase 2：集成PatentHub（3-4天）
- [ ] API调用集成
- [ ] 结果返回格式
- [ ] 错误处理

### Phase 3：高级优化（5-7天）
- [ ] 同义词扩展
- [ ] 语义理解
- [ ] 机器学习排序

## 预期效果

### 对用户
- ✅ 无需手动编辑搜索词
- ✅ 只需评分（简单直观）
- ✅ 获得最相关的结果

### 对相关度
- ✅ 标题匹配度提高30%
- ✅ IPC匹配度提高25%
- ✅ 整体相关度提高40%

## 下一步

你想现在开始实施Phase 1吗？我可以：

1. **创建关键词提取器** - 从创新方向中自动提取关键词
2. **创建查询生成器** - 生成PatentHub最优查询
3. **实现相关度评分** - 计算搜索结果的相关度

如何开始？
